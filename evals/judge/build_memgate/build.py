"""Scratch builder for ~/AI/jev/evals/judge/memgate_cases.json (not committed)."""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path.home() / "PycharmProjects/cross-memory"
LIVE_ROOT = REPO / "memory-store"
PRE_AUDIT = "914cd27"  # trading-bot store as imported, before the 2c296be audit
AUDIT = "2c296be"


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True, text=True).stdout


def run_at(commit, store, run_id):
    month = run_id[:7]
    return json.loads(git("show", f"{commit}:memory-store/{store}/memory/runs/{month}/{run_id}.json"))


def snapshot(commit, cutoff):
    """Temp store root holding every run at `commit` with timestamp < cutoff."""
    root = Path(tempfile.mkdtemp(prefix="snap_"))
    files = [f for f in git("ls-tree", "-r", "--name-only", commit, "memory-store").splitlines() if "/runs/" in f]
    for f in files:
        rec = json.loads(git("show", f"{commit}:{f}"))
        if rec["timestamp"] < cutoff:
            dest = root / f.removeprefix("memory-store/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    for mem in root.glob("*/memory"):
        subprocess.run(["cross-memory", "reindex", "--memory-dir", str(mem)], check=True, capture_output=True,
                       env={**os.environ, "CROSS_MEMORY_AUTOSYNC": "0"}, cwd="/tmp")
    return root


def query(task, root=LIVE_ROOT, store="ai", limit=5):
    env = {**os.environ, "CROSS_MEMORY_AUTOSYNC": "0", "CROSS_MEMORY_STORE_ROOT": str(root)}
    out = subprocess.run(["cross-memory", "query", "--memory-dir", str(root / store / "memory"), "--limit", str(limit), task],
                         check=True, capture_output=True, text=True, env=env, cwd="/tmp").stdout
    return out


def split(text):
    """(header lines, [block lines]) of cross-memory query output."""
    header, blocks = [], []
    for line in text.rstrip("\n").splitlines():
        if re.match(r"\d+\.\s", line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            header.append(line)
    return header, blocks


def join(header, blocks):
    lines = list(header)
    for i, b in enumerate(blocks, 1):
        lines.append(re.sub(r"^\d+\.", f"{i}.", b[0]))
        lines.extend(b[1:])
    text = "\n".join(lines)
    return re.sub(r"\((\d+) of (\d+) in memory\)", lambda m: f"({len(blocks)} of {m.group(2)} in memory)", text)


def frozen(task, root=LIVE_ROOT, store="ai", target=None, drop=()):
    """Query output for `task`; drops entries whose head contains any of `drop`, and makes sure
    the entry whose head contains `target` is present (replacing the least relevant one if not).
    Returns (existing text, exact head line of the target or None)."""
    header, blocks = split(query(task, root, store))
    blocks = [b for b in blocks if not any(d in b[0] for d in drop)]
    if target and not any(target in b[0] for b in blocks):
        _, wide = split(query(task, root, store, limit=100))
        found = [b for b in wide if target in b[0]]
        if not found:
            # No keyword overlap at all: take the entry from a query on its own task text.
            _, own = split(query(target, root, store, limit=100))
            found = [b for b in own if target in b[0]]
            # Its match score there is against another query; mark it as substituted.
            found[0][0] = re.sub(r"\(match [\d.]+\)", "(match 0.00)", found[0][0])
        if len(blocks) >= 5:
            blocks[-1] = found[0]
        else:
            blocks.append(found[0])
        substituted = True
    else:
        substituted = False
    text = join(header, blocks)
    head = None
    if target:
        heads = [re.sub(r"^\d+\.", "", b[0]).strip() for b in blocks]
        idx = next(i for i, h in enumerate(heads) if target in h)
        head = text.splitlines()[len(header) + sum(len(b) for b in blocks[:idx])].strip()
    return text, head, substituted
