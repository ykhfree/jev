"""Offline evaluation: can Jev find UI elements in screenshots (Box + presence Noul), and pick
the screens that show something? Ground truth is the DOM box of each fixture target.

Arms:
  jev_box    one request on the full screenshot: presence Noul + Box
  jev_zoom   jev_box, then one Box request on a higher-resolution crop around its box
  jev_verify jev_box, then one Noul on the full screenshot with a marker drawn at its click point:
             does the marker sit on the target? (flags likely misses)
  claude     Claude reads the same screenshot and answers presence + pixel box (claude -p)
  which_jev  one presence Noul per (screen, query), ranked like `jev rank`
  which_cl   Claude sees all screens at once and names the ones that show the query

Every model call is cached in cache.json keyed on its inputs, so re-runs are free.
Run with the jev venv: ~/.local/pipx/venvs/jev/bin/python eval_vision.py [--render]
"""

import hashlib
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image as PILImage
from typesafe_sdk import Image, TypeSafeClient

import jev
from pages import LOCATE_CASES, PAGES, WHICH_CASES

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # evals/, for evalkit
from evalkit import Cache, run_claude  # noqa: E402

HERE = Path(__file__).parent
SHOTS = HERE / "shots"
MODEL, HEADERS = jev.VISION_MODEL, jev.VISION_HEADERS
CLAUDE_MODEL = "opus"
PRESENT = 0.5  # presence Noul cut; fixed before the run, not tuned
CLAUDE_MAX_PIXELS = 1_150_000  # Claude downsizes larger images; stay under so pixel answers map back
ZOOM_FACTOR, ZOOM_MIN = 3.0, 0.3  # crop = 3x the box, at least 30% of each side

CLAUDE_SYSTEM = "You locate user-interface elements in screenshots. Reply with JSON only, no prose."


# --- geometry (pure, unit-tested) ---

def hit(box, truth):
    """True when the box's center (the click point) falls inside the truth box."""
    x, y = jev.box_center(box)
    return truth["left"] <= x <= truth["right"] and truth["top"] <= y <= truth["bottom"]


def iou(a, b):
    w = max(0.0, min(a["right"], b["right"]) - max(a["left"], b["left"]))
    h = max(0.0, min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]))
    inter = w * h
    area = lambda r: (r["right"] - r["left"]) * (r["bottom"] - r["top"])  # noqa: E731
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def zoom_region(box):
    """A region around `box`, ZOOM_FACTOR times its size and at least ZOOM_MIN, kept inside the image."""
    x, y = jev.box_center(box)
    region = {}
    for lo, hi, c in (("left", "right", x), ("top", "bottom", y)):
        size = min(1.0, max(ZOOM_FACTOR * (box[hi] - box[lo]), ZOOM_MIN))
        start = min(max(c - size / 2, 0.0), 1.0 - size)
        region[lo], region[hi] = start, start + size
    return region


def to_full(box, region):
    """Map a box given as fractions of `region` back to fractions of the full image."""
    w, h = region["right"] - region["left"], region["bottom"] - region["top"]
    return {
        "left": region["left"] + box["left"] * w, "right": region["left"] + box["right"] * w,
        "top": region["top"] + box["top"] * h, "bottom": region["top"] + box["bottom"] * h,
    }


def claude_size(w, h):
    scale = min(1.0, jev.IMAGE_MAX / max(w, h), (CLAUDE_MAX_PIXELS / (w * h)) ** 0.5)
    return round(w * scale), round(h * scale)


def parse_claude(text, w, h):
    """Claude's JSON reply -> (present, box as fractions or None). Unparseable -> (None, None)."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("present"), bool):
        return None, None
    b = data.get("box")
    if not (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)):
        return data["present"], None
    return data["present"], {"left": b[0] / w, "top": b[1] / h, "right": b[2] / w, "bottom": b[3] / h}


# --- images ---

def render():
    """Render every fixture page at its device scale and record DOM boxes as viewport fractions."""
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(exist_ok=True)
    truth = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for name, (w, h, dpr, html) in PAGES.items():
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=dpr)
            page.set_content(html)
            page.screenshot(path=str(SHOTS / f"{name}.png"))
            truth[name] = {}
            for el in page.query_selector_all("[data-t]"):
                r = el.bounding_box()
                truth[name][el.get_attribute("data-t")] = {
                    "left": r["x"] / w, "top": r["y"] / h,
                    "right": (r["x"] + r["width"]) / w, "bottom": (r["y"] + r["height"]) / h,
                }
            page.close()
        browser.close()
    (HERE / "truth.json").write_text(json.dumps(truth, indent=1))


def png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def shot(page, region=None, sizer=jev.image_size):
    """The page screenshot (optionally cropped to a fractional region), resized by `sizer`."""
    img = PILImage.open(SHOTS / f"{page}.png").convert("RGB")
    if region:
        W, H = img.size
        img = img.crop((round(region["left"] * W), round(region["top"] * H),
                        round(region["right"] * W), round(region["bottom"] * H)))
    return img.resize(sizer(*img.size), PILImage.LANCZOS)


def sha(data):
    return hashlib.sha256(data).hexdigest()


# --- model calls ---

_client = []  # created on first call, so offline tests need no API key


def ask_jev(cache, image, questions):
    """One Jev request with the image as `screen`. Returns {id: noul float | box dict}."""
    data = png(image)
    key = ["jev", MODEL, sha(data), {k: [type(q).__name__, q.instructions] for k, q in questions.items()}]

    def call():
        t0 = time.time()
        if not _client:
            _client.append(TypeSafeClient())
        res = _client[0].system_one(state={"screen": Image(data)}, questions=questions, model=MODEL, extra_headers=HEADERS)
        out = {k: a.noul for k, a in res.nouls.items()}
        out.update({k: {**a.box.model_dump(), "confidence": a.confidence} for k, a in res.boxes.items()})
        return {"answers": out, "model": res.model, "input_tokens": res.usage.input_tokens, "sec": round(time.time() - t0, 2)}

    return cache.get(key, call)


def jev_box(cache, page, desc):
    r = ask_jev(cache, shot(page), {"present": jev.shows_question(desc), "where": jev.box_question(desc)})
    return r["answers"]["present"], r["answers"]["where"], r


def jev_zoom(cache, page, desc, first_box):
    region = zoom_region(first_box)
    r = ask_jev(cache, shot(page, region), {"where": jev.box_question(desc)})
    box = r["answers"]["where"]
    return {**to_full(box, region), "confidence": box["confidence"]}, r


def jev_verify(cache, page, desc, first_box):
    q = jev.marker_question(desc)
    return ask_jev(cache, jev.with_marker(shot(page), first_box), {"on_target": q})["answers"]["on_target"]


def claude_locate(cache, page, desc):
    image = shot(page, sizer=claude_size)
    w, h = image.size
    text = (f"The image is {w}x{h} pixels. Find {desc}. Reply with exactly one JSON object: "
            '{"present": true or false, "box": [left, top, right, bottom]} in pixel coordinates of this image, '
            'with "box": null when it is not shown.')
    data = png(image)
    r = cache.get(["claude", CLAUDE_MODEL, CLAUDE_SYSTEM, text, sha(data)],
                  lambda: run_claude(CLAUDE_SYSTEM, text, CLAUDE_MODEL, json_output=True, images=[data]))
    return (*parse_claude(r["text"], w, h), r)


def claude_which(cache, desc):
    names = list(PAGES)
    images = [png(shot(n, sizer=claude_size)) for n in names]
    listing = ", ".join(f"image {i + 1} = {n}" for i, n in enumerate(names))
    text = (f"The images are, in order: {listing}. Which screens show {desc}? Reply with exactly one JSON object: "
            '{"screens": [names]}, using the names above; an empty list when none shows it.')
    r = cache.get(["claude_which", CLAUDE_MODEL, CLAUDE_SYSTEM, text, [sha(i) for i in images]],
                  lambda: run_claude(CLAUDE_SYSTEM, text, CLAUDE_MODEL, json_output=True, images=images))
    m = re.search(r"\{.*\}", r["text"], re.S)
    try:
        picked = set(json.loads(m.group(0))["screens"]) if m else None
    except (json.JSONDecodeError, KeyError, TypeError):
        picked = None
    return picked, r


# --- run ---

def pmap(fn, items, workers=4):
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(fn, items))


def locate_row(cache, truth, case):
    cid, page, target, desc = case
    gold = truth[page][target] if target else None
    p, box, r1 = jev_box(cache, page, desc)
    row = {"id": cid, "page": page, "gold_present": gold is not None,
           "jev_present": p, "jev_conf": box["confidence"], "jev_sec": r1["sec"], "jev_tokens": r1["input_tokens"]}
    if gold:
        row.update(jev_hit=hit(box, gold), jev_iou=round(iou(box, gold), 3))
        zbox, r2 = jev_zoom(cache, page, desc, box)
        row.update(zoom_hit=hit(zbox, gold), zoom_iou=round(iou(zbox, gold), 3), zoom_conf=zbox["confidence"],
                   zoom_tokens=r2["input_tokens"], verify=jev_verify(cache, page, desc, box))
    c_present, c_box, rc = claude_locate(cache, page, desc)
    row.update(cl_present=c_present, cl_cost=rc["cost_usd"], cl_ms=rc["duration_ms"])
    if gold:
        row.update(cl_hit=bool(c_box) and hit(c_box, gold), cl_iou=round(iou(c_box, gold), 3) if c_box else 0.0)
    return row


def which_row(cache, case):
    cid, desc, gold = case
    scores = dict(zip(PAGES, pmap(lambda n: ask_jev(cache, shot(n), {"present": jev.shows_question(desc)})["answers"]["present"], PAGES)))
    ranked = sorted(scores, key=scores.get, reverse=True)
    picked_cl, rc = claude_which(cache, desc)
    return {
        "id": cid, "gold": sorted(gold), "scores": {k: round(v, 3) for k, v in scores.items()},
        "jev_top1_ok": (ranked[0] in gold) if gold else scores[ranked[0]] < PRESENT,
        "jev_set": sorted(n for n in PAGES if scores[n] >= PRESENT),
        "cl_set": sorted(picked_cl) if picked_cl is not None else None, "cl_cost": rc["cost_usd"],
    }


def rate(rows, key, subset=lambda r: True):
    picked = [r for r in rows if subset(r) and key in r]
    n = sum(bool(r[key]) for r in picked)
    return f"{n}/{len(picked)} ({n / len(picked):.0%})" if picked else "-"


def mean(rows, key):
    vals = [r[key] for r in rows if key in r]
    return f"{sum(vals) / len(vals):.2f}" if vals else "-"


def flagged(rows, hits):
    picked = [r for r in rows if r["jev_hit"] == hits]
    return f"{sum(r['verify'] < PRESENT for r in picked)}/{len(picked)}"


def report(loc, which):
    present = [r for r in loc if r["gold_present"]]
    for r in loc:
        r["jev_present_ok"] = (r["jev_present"] >= PRESENT) == r["gold_present"]
        r["cl_present_ok"] = r["cl_present"] == r["gold_present"]
    pairs = [(w, n) for w in which for n in PAGES]
    jev_pair = sum((w["scores"][n] >= PRESENT) == (n in w["gold"]) for w, n in pairs)
    cl_pair = sum(w["cl_set"] is not None and (n in w["cl_set"]) == (n in w["gold"]) for w, n in pairs)
    lines = [
        "# Vision eval report", "",
        f"Model `{MODEL}`, Claude `{CLAUDE_MODEL}`. {len(loc)} locate cases ({len(present)} present), "
        f"{len(which)} which queries x {len(PAGES)} screens.", "",
        "## Locate", "",
        "| metric | jev_box | jev_zoom | claude |", "|---|---|---|---|",
        f"| presence correct | {rate(loc, 'jev_present_ok')} | (same) | {rate(loc, 'cl_present_ok')} |",
        f"| click point inside target | {rate(present, 'jev_hit')} | {rate(present, 'zoom_hit')} | {rate(present, 'cl_hit')} |",
        f"| mean IoU | {mean(present, 'jev_iou')} | {mean(present, 'zoom_iou')} | {mean(present, 'cl_iou')} |",
        f"| mean latency | {mean(loc, 'jev_sec')} s | +1 request | {mean([{**r, 's': r['cl_ms'] / 1000} for r in loc], 's')} s |",
        f"| mean input tokens / cost | {mean(loc, 'jev_tokens')} tok | +{mean(present, 'zoom_tokens')} tok "
        f"| ${mean(loc, 'cl_cost')} |", "",
        f"Marker verify (flag when < {PRESENT}): flags {flagged(present, False)} jev_box misses "
        f"and {flagged(present, True)} jev_box hits.", "",
        "| case | jev hit | conf | verify | zoom hit | zoom conf | claude hit |", "|---|---|---|---|---|---|---|",
        *[f"| {r['id']} | {r['jev_hit']} | {r['jev_conf']:.2f} | {r['verify']:.2f} | {r['zoom_hit']} | {r['zoom_conf']:.2f} "
          f"| {r['cl_hit']} |" for r in present],
        "", "| absent case | jev presence | claude presence |", "|---|---|---|",
        *[f"| {r['id']} | {r['jev_present']:.3f} | {r['cl_present']} |" for r in loc if not r["gold_present"]],
        "", "## Which", "",
        f"Per (query, screen) pair correct: Jev {jev_pair}/{len(pairs)}, Claude {cl_pair}/{len(pairs)}. "
        f"Jev top-1 (or no_match) correct: {rate(which, 'jev_top1_ok')}. Claude mean cost per query ${mean(which, 'cl_cost')}.", "",
        "| query | gold | jev >= 0.5 | claude |", "|---|---|---|---|",
        *[f"| {w['id']} | {w['gold']} | {w['jev_set']} | {w['cl_set']} |" for w in which],
    ]
    return "\n".join(lines) + "\n"


def main():
    if "--render" in sys.argv or not (HERE / "truth.json").exists():
        render()
    truth = json.loads((HERE / "truth.json").read_text())
    cache = Cache(HERE / "cache.json")
    loc = pmap(lambda c: locate_row(cache, truth, c), LOCATE_CASES)
    which = [which_row(cache, c) for c in WHICH_CASES]
    (HERE / "results.json").write_text(json.dumps({"locate": loc, "which": which}, indent=1))
    (HERE / "report.md").write_text(report(loc, which))
    print((HERE / "report.md").read_text())


if __name__ == "__main__":
    main()
