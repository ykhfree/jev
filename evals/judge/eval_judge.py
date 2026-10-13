"""Offline evaluation: should `jev claims` and `jev memgate` stay in the "Jev decides" tier of
~/.claude/CLAUDE.md, or does Claude judging directly do as well? The design and decision rule
were pre-registered in findings.md; this script produces the numbers that rule needs.

Arms:
  claims   jev             the real jev.check_claim path: Jev's relation judgment on the quote's
                           section (±CLAIM_CONTEXT_LINES)
           claude_section  Claude on exactly the section Jev is sent
           claude_file     Claude on the whole file: the realistic alternative, Claude re-opening it
           claude_rep      second independent sample of claude_file: the noise floor
  memgate  jev             the real jev.cmd_memgate path
           claude          Claude on the same record and the same existing entries
           claude_rep      second independent sample of claude: the noise floor

Every model call is cached in cache.json keyed on its inputs, so re-runs are free.
Run with the jev venv: cd evals/judge && ~/.local/pipx/venvs/jev/bin/python eval_judge.py
"""

import json
import re
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import jev

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # evals/, for evalkit
from evalkit import Cache, accuracy, flips, run_claude  # noqa: E402

HERE = Path(__file__).resolve().parent
CLAUDE_MODEL = "opus"

RELATIONS = list(jev.RELATION_QUESTION.criteria)  # supports, contradicts, says_nothing
VERDICTS = list(jev.RELATION_TO_VERDICT.values())  # verified, contradicted, unsupported
MEMGATE_LABELS = ["conflict", "duplicate", "skip", "record"]  # jev.memgate_verdict's precedence
CLAIMS_TIER = {"verified", "contradicted"}  # acted on without review when review is false
MEMGATE_TIER = {"record", "skip", "duplicate"}  # acted on without review; conflict/uncertain are not
LOST = {"skip", "duplicate"}  # memgate verdicts that drop the record
CLAUDE_ARMS = {"claims": ["claude_section", "claude_file", "claude_rep"], "memgate": ["claude", "claude_rep"]}

# --- Claude prompts, built from jev's own question text so both judges get the same rubric ---
def one_of(labels) -> str:
    return ", ".join(labels[:-1]) + f", or {labels[-1]}"


def claims_system(given: str) -> str:
    options = "\n".join(f"- {label}: {text}" for label, text in jev.RELATION_QUESTION.criteria.items())
    return (
        "You check a claim that a coding agent made about a file.\n"
        f"The input gives `claim` and {given}.\n\n"
        f"{jev.RELATION_QUESTION.instructions}\n{options}\n\n"
        f"Reply with exactly one word: {one_of(RELATIONS)}."
    )


CLAIMS_SECTION_SYSTEM = claims_system("`section`, the lines of the file around the quoted evidence")
CLAIMS_FILE_SYSTEM = claims_system("`content`, the whole of the file named `file`; below, the section is `content`")


def memgate_system() -> str:
    def questions(nouls: dict) -> str:
        lines = []
        for key, noul in nouls.items():
            line = f"- {key}: {noul.instructions}"
            if noul.criteria:
                line += f" (yes: {noul.criteria['true']}; no: {noul.criteria['false']})"
            lines.append(line)
        return "\n".join(lines)

    return f"""You decide whether a coding agent should save `record` to its memory of past runs.
The input gives `record` and `existing`, the stored records most similar to it (possibly none).

Questions about `record`:
{questions(jev.MEMGATE_QUESTIONS)}

Questions for each entry of `existing`, where `existing` below means that one entry:
{questions(jev.MEMGATE_PAIR_QUESTIONS)}

Verdict; the first that applies wins (conflict > duplicate > skip > record):
- conflict: `conflict` is yes for any entry
- duplicate: `duplicate` is yes for any entry
- skip: `reuse`, `durable` or `actionable` is no, or `noise` is yes
- record: none of the above

Reply with exactly one word: {one_of(MEMGATE_LABELS)}."""


MEMGATE_SYSTEM = memgate_system()


def parse_label(text: str, labels) -> str | None:
    """The one label `text` names; None when it names none or several different ones."""
    found = re.findall(r"\b(?:" + "|".join(map(re.escape, labels)) + r")\b", text.lower())
    return found[0] if len(set(found)) == 1 else None


def claim_verdict(text: str) -> str | None:
    return jev.RELATION_TO_VERDICT.get(parse_label(text, RELATIONS))


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


# --- Cached model calls ---
def cached_ask(cache: Cache, ask, seconds: list):
    """`ask` served from the cache. Appends each request's wall time to `seconds`; a cache hit
    reports the time its original, uncached call took."""

    def cached(state, questions):
        def timed():
            start = time.perf_counter()
            answers = ask(state, questions)
            return {"answers": answers, "seconds": round(time.perf_counter() - start, 3)}

        entry = cache.get(["jev", state, repr(questions)], timed)
        seconds.append(entry["seconds"])
        return entry["answers"]

    return cached


def ask_claude(cache: Cache, arm: str, system: str, text: str) -> dict:
    # `arm` is in the key so claude_rep samples independently of the arm it repeats
    return cache.get(
        ["claude", arm, CLAUDE_MODEL, system, text],
        lambda: run_claude(system, text, CLAUDE_MODEL, json_output=True),
    )


def claude_fields(outputs: dict, parse) -> dict:
    return {
        **{arm: parse(out["text"]) for arm, out in outputs.items()},
        "raw": {arm: out["text"] for arm, out in outputs.items()},
        "usage": {arm: {k: v for k, v in out.items() if k != "text"} for arm, out in outputs.items()},
    }


# --- Cases ---
def is_clear(label: dict | None, expected: dict) -> bool:
    """The blind annotator gave the gold label(s) and did not flag the case ambiguous."""
    return label is not None and not label["ambiguous"] and all(label[k] == v for k, v in expected.items())


def memgate_args(case: dict, existing_path: str):
    """Parse the case through jev's own CLI parser, so it is validated as a real call would be.
    `--flag=value` keeps a learning that starts with '-' from reading as an option."""
    argv = [
        "memgate",
        f"--task={case['task']}",
        f"--result={case['result']}",
        *(f"--learning={learning}" for learning in case["learnings"]),
        f"--existing={existing_path}",
    ]
    if case["outcome"]:
        argv.append(f"--outcome={case['outcome']}")
    return jev.build_parser().parse_args(argv)


def check_cases(claims: list, memgate: list) -> None:
    """Raise, listing every broken case, before any paid call is made."""
    bad = [f"duplicate id {i}" for i, n in Counter(c["id"] for c in claims + memgate).items() if n > 1]
    for c in claims:
        path = HERE / c["file"]
        if not {c["gold_section"], c["gold_file"]} <= set(VERDICTS):
            bad.append(f"{c['id']}: gold not in {VERDICTS}")
        elif not path.is_file():
            bad.append(f"{c['id']}: no file {path}")
        elif jev.locate_quote(jev.read_text(str(path)), c["quote"]) is None:
            bad.append(f"{c['id']}: quote not found in {c['file']}")
    for c in memgate:
        if c["gold"] not in MEMGATE_LABELS:
            bad.append(f"{c['id']}: gold not in {MEMGATE_LABELS}")
        try:
            memgate_args(c, "-")
        except SystemExit:
            bad.append(f"{c['id']}: rejected by jev's memgate argument parser (reason on stderr)")
    if bad:
        raise ValueError("broken cases:\n" + "\n".join(bad))


# --- Runs ---
def run_claims(cases: list, labels: dict, ask, cache: Cache) -> list:
    def one(case):
        text = jev.read_text(str(HERE / case["file"]))
        first, last = jev.locate_quote(text, case["quote"])  # check_cases guarantees a match
        section = jev.claim_section(text, first, last)
        seconds = []
        claim = {"claim": case["claim"], "file": str(HERE / case["file"]), "quote": case["quote"]}
        out = jev.check_claim(claim, cached_ask(cache, ask, seconds))
        whole = dumps({"claim": case["claim"], "file": case["file"], "content": text})
        outputs = {
            "claude_section": ask_claude(cache, "claude_section", CLAIMS_SECTION_SYSTEM,
                                         dumps({"claim": case["claim"], "section": section})),
            "claude_file": ask_claude(cache, "claude_file", CLAIMS_FILE_SYSTEM, whole),
            "claude_rep": ask_claude(cache, "claude_rep", CLAIMS_FILE_SYSTEM, whole),
        }
        expected = {"label_section": case["gold_section"], "label_file": case["gold_file"]}
        return {
            "id": case["id"],
            "kind": case["kind"],
            "gold_section": case["gold_section"],
            "gold_file": case["gold_file"],
            "clear": is_clear(labels.get(case["id"]), expected),
            "jev": out["verdict"],
            "jev_confidence": out["confidence"],
            "jev_review": out["review"],
            "jev_seconds": seconds,
            **claude_fields(outputs, claim_verdict),
        }

    return jev.pmap(one, cases)


def run_memgate(cases: list, labels: dict, ask, cache: Cache) -> list:
    def one(case):
        seconds = []
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "existing.txt"
            existing.write_text(case["existing"], encoding="utf-8")
            args = memgate_args(case, str(existing))
            out = jev.cmd_memgate(args, cached_ask(cache, ask, seconds))
        text = dumps({"record": jev.memgate_record(args), "existing": jev.parse_numbered(case["existing"])})
        outputs = {arm: ask_claude(cache, arm, MEMGATE_SYSTEM, text) for arm in CLAUDE_ARMS["memgate"]}
        return {
            "id": case["id"],
            "gold": case["gold"],
            "clear": is_clear(labels.get(case["id"]), {"label": case["gold"]}),
            "jev": out["verdict"],
            "jev_detail": {k: out[k] for k in ("scores", "duplicates", "conflicts")},
            "jev_seconds": seconds,
            **claude_fields(outputs, lambda t: parse_label(t, MEMGATE_LABELS)),
        }

    return jev.pmap(one, cases)


# --- Scoring ---
def claims_autonomous(row) -> bool:
    return not row["jev_review"] and row["jev"] in CLAIMS_TIER


def memgate_autonomous(row) -> bool:
    return row["jev"] in MEMGATE_TIER


def ids(rows, keep) -> list:
    return [r["id"] for r in rows if keep(r)]


def veto_errors(rows) -> list:
    """Autonomous-tier claims Jev called verified that are false (gold_file contradicted)."""
    return ids(rows, lambda r: claims_autonomous(r) and r["gold_file"] == "contradicted" and r["jev"] == "verified")


def unsupported_unreviewed(rows) -> list:
    return ids(rows, lambda r: r["jev"] == "unsupported" and not r["jev_review"])


def learnings_lost(rows, arm) -> list:
    return ids(rows, lambda r: r["gold"] == "record" and r[arm] in LOST)


def pct(hits: int, n: int) -> str:
    return f"{hits}/{n} ({hits / n:.0%})" if n else "-"


def listed(found: list) -> str:
    return f"{len(found)} {found}"


def distribution(rows, key) -> str:
    return ", ".join(f"{label} {n}" for label, n in Counter(r[key] for r in rows).most_common())


def confusion(rows, arm, gold, labels) -> list[str]:
    """Gold per row, picked per column; None is an unparsed Claude output."""
    counts = Counter((r[gold], r[arm]) for r in rows)
    columns = labels + sorted({p for _, p in counts if p not in labels}, key=str)
    lines = [f"{arm} (rows: {gold}, columns: picked)", "",
             "| gold \\ picked | " + " | ".join(map(str, columns)) + " |", "|---" * (len(columns) + 1) + "|"]
    lines += [f"| {g} | " + " | ".join(str(counts[g, p]) for p in columns) + " |" for g in labels]
    return lines + [""]


def noise_floor(rows, before, after, gold) -> str:
    changed = ids(rows, lambda r: r[before] != r[after])
    fixed, broken = flips(rows, before, after, gold)
    return (f"{before} -> {after}: changed {listed(changed)}; against {gold}: "
            f"fixed {listed(fixed)}, broken {listed(broken)}")


CLAIMS_SCORED = [("jev", "gold_section"), ("claude_section", "gold_section"),
                 ("claude_file", "gold_file"), ("claude_rep", "gold_file")]


def claims_block(rows, name) -> list[str]:
    tier = [r for r in rows if claims_autonomous(r)]
    lines = [f"### claims: {name} cases (n={len(rows)})", "",
             "| arm | scored against | accuracy |", "|---|---|---|"]
    lines += [f"| {arm} | {gold} | {accuracy(rows, arm, gold=gold)} |" for arm, gold in CLAIMS_SCORED]
    lines += [
        "",
        "Jev autonomous tier (review false, verdict verified or contradicted), scored against gold_file:",
        f"- coverage: {pct(len(tier), len(rows))}",
        f"- jev accuracy: {accuracy(tier, 'jev', gold='gold_file')}",
        f"- claude_file accuracy on the same cases: {accuracy(tier, 'claude_file', gold='gold_file')}",
        f"- veto errors (gold_file contradicted -> jev verified): {listed(veto_errors(rows))}",
        f"- jev unsupported with review false (no action defined for these): {listed(unsupported_unreviewed(rows))}",
        "",
        "| kind | n | jev vs gold_section | claude_file vs gold_file |",
        "|---|---|---|---|",
    ]
    for kind in sorted({r["kind"] for r in rows}):
        of_kind = [r for r in rows if r["kind"] == kind]
        lines.append(f"| {kind} | {len(of_kind)} | {accuracy(of_kind, 'jev', gold='gold_section')} "
                     f"| {accuracy(of_kind, 'claude_file', gold='gold_file')} |")
    lines.append("")
    for arm, gold in CLAIMS_SCORED[:3]:
        lines += confusion(rows, arm, gold, VERDICTS)
    return lines + [noise_floor(rows, "claude_file", "claude_rep", "gold_file"), ""]


def memgate_block(rows, name) -> list[str]:
    tier = [r for r in rows if memgate_autonomous(r)]
    gold_conflicts = [r for r in rows if r["gold"] == "conflict"]
    precision = ", ".join(
        f"{v} {pct(sum(r['gold'] == v for r in tier if r['jev'] == v), sum(r['jev'] == v for r in tier))}"
        for v in ["record", "skip", "duplicate"]
    )
    lines = [
        f"### memgate: {name} cases (n={len(rows)})",
        "",
        f"- gold: {distribution(rows, 'gold')}",
        f"- jev verdicts: {distribution(rows, 'jev')}",
        "",
        "Jev autonomous tier (verdict record, skip or duplicate):",
        f"- coverage: {pct(len(tier), len(rows))}",
        f"- jev accuracy: {accuracy(tier, 'jev')}",
        f"- claude accuracy on the same cases: {accuracy(tier, 'claude')}",
        f"- jev precision per verdict: {precision}",
        "",
        f"All {name} cases:",
        f"- jev accuracy, every verdict (uncertain counts as wrong): {accuracy(rows, 'jev')}",
        f"- claude accuracy: {accuracy(rows, 'claude')}",
        f"- conflict recall: jev {accuracy(gold_conflicts, 'jev')}, claude {accuracy(gold_conflicts, 'claude')}",
        f"- learnings lost (gold record -> skip or duplicate): jev {listed(learnings_lost(rows, 'jev'))}, "
        f"claude {listed(learnings_lost(rows, 'claude'))}",
        "",
    ]
    for arm in ["jev", "claude"]:
        lines += confusion(rows, arm, "gold", MEMGATE_LABELS)
    return lines + [noise_floor(rows, "claude", "claude_rep", "gold"), ""]


USAGE_FORMATS = [("input_tokens", ".0f"), ("cache_read_tokens", ".0f"), ("cache_creation_tokens", ".0f"),
                 ("output_tokens", ".0f"), ("cost_usd", ".4f"), ("duration_ms", ".0f")]


def median_total(values, spec: str) -> str:
    return f"{statistics.median(values):{spec}} / {sum(values):{spec}}" if values else "-"


def cost_block(results: dict) -> list[str]:
    lines = ["## Cost (all cases)", "", "Claude, per case: median / total over cases", "",
             "| command | arm | " + " | ".join(k for k, _ in USAGE_FORMATS) + " |",
             "|---" * (len(USAGE_FORMATS) + 2) + "|"]
    for command, rows in results.items():
        for arm in CLAUDE_ARMS[command]:
            cells = [median_total([r["usage"][arm][k] for r in rows], spec) for k, spec in USAGE_FORMATS]
            lines.append(f"| {command} | {arm} | " + " | ".join(cells) + " |")
    lines += ["", "Jev (seconds are the uncached wall time of each request; a case's requests run in parallel)", "",
              "| command | requests per case, median | seconds per request, median "
              "| summed request seconds per case: median / total |", "|---|---|---|---|"]
    for command, rows in results.items():
        per_case = [r["jev_seconds"] for r in rows]
        requests = [s for case in per_case for s in case]
        per_request = f"{statistics.median(requests):.2f}" if requests else "-"
        count = f"{statistics.median(len(c) for c in per_case):g}" if per_case else "-"
        lines.append(f"| {command} | {count} | {per_request} | {median_total([sum(c) for c in per_case], '.2f')} |")
    return lines


def report(results: dict) -> str:
    claims, memgate = results["claims"], results["memgate"]
    lines = [
        "# Judge eval: Jev vs Claude on claims and memgate",
        "",
        "Generated by eval_judge.py; the decision rule is pre-registered in findings.md.",
        "clear = the blind annotator's label(s) equal gold and the case is not flagged ambiguous.",
        f"claims: {len(claims)} cases, {sum(r['clear'] for r in claims)} clear. "
        f"memgate: {len(memgate)} cases, {sum(r['clear'] for r in memgate)} clear.",
        "",
        "## claims",
        "",
    ]
    for name, keep in [("clear", lambda r: r["clear"]), ("all", lambda r: True)]:
        lines += claims_block([r for r in claims if keep(r)], name)
    lines += ["## memgate", ""]
    for name, keep in [("clear", lambda r: r["clear"]), ("all", lambda r: True)]:
        lines += memgate_block([r for r in memgate if keep(r)], name)
    lines += cost_block(results)
    unparsed = [(command, r["id"], arm, r["raw"][arm][:80])
                for command, rows in results.items() for r in rows for arm in CLAUDE_ARMS[command] if r[arm] is None]
    if unparsed:
        lines += ["", "## Unparsed Claude outputs (scored as wrong)", ""]
        lines += [f"- {command} {case_id} {arm}: {text!r}" for command, case_id, arm, text in unparsed]
    return "\n".join(lines)


def main():
    def load(name):
        return json.loads((HERE / name).read_text())

    claims, memgate = load("claims_cases.json"), load("memgate_cases.json")
    labels = load("labels_independent.json")
    check_cases(claims, memgate)
    cache = Cache(HERE / "cache.json")
    ask = jev.make_ask()
    results = {
        "claims": run_claims(claims, {x["id"]: x for x in labels["claims"]}, ask, cache),
        "memgate": run_memgate(memgate, {x["id"]: x for x in labels["memgate"]}, ask, cache),
    }
    (HERE / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    text = report(results)
    (HERE / "report.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    sys.exit(main())
