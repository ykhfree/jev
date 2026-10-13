"""Offline evaluation: can Jev route a coding-agent task the way the Orchestration
rules in ~/.claude/CLAUDE.md say to? Follows the skill_suggestion cookbook shape.

Arms:
  jev         Jev Choice, state = request + recent_context
  jev_prompt  Jev Choice, request only (all a prompt-only hook would see)
  jev_rules   Jev Nouls composed in code in rule order, request + recent_context
  claude      Claude classifier alone (claude -p, isolated from user settings)
  claude_rep  second independent sample of `claude`: the noise floor for fixed/broken
  claude_jev  Claude with Jev's suggestion appended
  claude_wrong Claude with a confidently wrong suggestion (clear cases): the harm test
  jev_raw     Jev Choice with a raw transcript tail as recent_context (raw_contexts.json, optional)

Every model call is cached in cache.json keyed on its inputs, so re-runs are free.
Run with the jev venv: ~/.local/pipx/venvs/jev/bin/python eval_route.py
"""

import hashlib
import json
import re
import subprocess
import sys
import threading
from collections import Counter
from pathlib import Path
from tempfile import gettempdir

from typesafe_sdk import Choice, Noul

import jev

HERE = Path(__file__).parent
LABELS = ["self", "deep-reasoner", "feature-developer", "fast-worker"]
GATE = 0.5  # confidence floor from the TypeSafe Confidence docs; fixed before the run, not tuned
NOUL_YES = 0.5
CLAUDE_MODEL = "opus"

POLICY = """Evaluate top to bottom; the first rule that matches wins.
1. The main session has already read every file the change touches, and can state the exact edit (file + what changes) in one or two sentences → do it yourself. Spawning an agent costs more.
2. The task locks in a costly-to-revert decision (architecture, DB schema, API contracts, migrations, technology choices) → if the options are still open, design with deep-reasoner.
3. How to solve it is still undecided — root cause unknown after one investigation pass, or two or more viable designs/algorithms to choose between → deep-reasoner.
4. The change decides what the product does — new or changed behavior, domain rules, edge-case handling → feature-developer (it writes the tests for the logic it adds).
5. The outcome is fully specified and only needs to be typed out — boilerplate, renames, formatting, the same edit across many files, tests whose cases are already listed → fast-worker.
A pure question or explanation that changes no code is answered by the main session itself."""

CLAUDE_SYSTEM = f"""You are the main session of a coding agent deciding who handles the user's latest request.
The input gives `request` (the user's latest message) and `recent_context` (what the session has already read, proposed, or tried; empty means nothing relevant). Numbered references in `request` point into `recent_context`.

Routing policy:
{POLICY}

Reply with exactly one word: self, deep-reasoner, feature-developer, or fast-worker."""

# --- Jev questions ---
ROUTE = Choice(
    instructions={
        "question": "Which handler should the main coding-agent session use for `request`?",
        "focus": "`recent_context` says what the session already read, proposed, or tried; "
        "numbered references in `request` point into it. The first matching option in this order wins: "
        "self, deep-reasoner, feature-developer, fast-worker.",
    },
    criteria={
        "self": {
            "what": "The main session handles it directly",
            "covers": [
                "a question or explanation that changes no code",
                "a small edit whose files the session already read and whose exact change is already stated",
            ],
        },
        "deep-reasoner": {
            "what": "How to solve it is still undecided and needs design or diagnosis",
            "covers": [
                "a costly-to-revert decision with options still open: architecture, DB schema, "
                "API contract, data migration, technology choice",
                "root cause still unknown after an investigation pass or after failed fixes",
                "two or more viable designs or algorithms to choose between",
            ],
        },
        "feature-developer": {
            "what": "The design is settled and the change decides what the product does",
            "covers": ["new or changed behavior", "domain rules", "edge-case handling"],
        },
        "fast-worker": {
            "what": "The outcome is fully specified and only needs to be typed out",
            "covers": [
                "boilerplate",
                "renames",
                "formatting",
                "the same edit across many files",
                "tests whose cases are already listed",
            ],
        },
    },
)

RULE_QUESTIONS = {
    "answer_only": Noul(
        instructions="Does `request` only ask for an answer or explanation, with no change to code, "
        "files, or configuration?"
    ),
    "exact_edit_known": Noul(
        instructions="According to `recent_context`, has the session already read the files involved "
        "and stated the exact small edit that `request` asks for?"
    ),
    "costly_decision_open": Noul(
        instructions="Does `request` require locking in a costly-to-revert decision (architecture, "
        "DB schema, API contract, data migration, technology choice) whose options are still open?"
    ),
    "approach_undecided": Noul(
        instructions="Is how to handle `request` still undecided: root cause unknown after "
        "investigation, or two or more viable designs or algorithms to choose between?"
    ),
    "changes_behavior": Noul(
        instructions="Does `request` add or change what the product does: its behavior, domain rules, "
        "or edge-case handling?"
    ),
    "fully_specified": Noul(
        instructions="Is the outcome of `request` fully specified so it only needs to be typed out: "
        "boilerplate, renames, formatting, the same edit across many files, or tests whose cases "
        "are already listed?"
    ),
}


def compose_rules(nouls: dict, fallback: str) -> str:
    """Apply the Orchestration rules in order to the Noul answers."""
    yes = {k: v >= NOUL_YES for k, v in nouls.items()}
    if yes["answer_only"] or yes["exact_edit_known"]:
        return "self"
    if yes["costly_decision_open"] or yes["approach_undecided"]:
        return "deep-reasoner"
    if yes["changes_behavior"]:
        return "feature-developer"
    if yes["fully_specified"]:
        return "fast-worker"
    return fallback


def suggestion_block(route: dict) -> str:
    """The cookbook's per-turn hint: advisory, and explicit when nothing stands out."""
    if route["confidence"] >= GATE:
        body = (
            f"Relevant handler for the current request: {route['choice']}. "
            "Ignore this if it does not fit what the user actually asked for."
        )
    else:
        body = "No handler stands out for this request."
    return f"\n\n<agent_relevance>\n{body}\n</agent_relevance>"


def plausible_wrong(probabilities: dict, gold: str) -> str:
    """The wrong label Jev itself rates highest: what a confident Jev mistake would suggest."""
    return max((label for label in LABELS if label != gold), key=lambda label: probabilities.get(label, 0.0))


def parse_label(text: str) -> str | None:
    found = re.findall(r"deep-reasoner|feature-developer|fast-worker|\bself\b", text.lower())
    return found[0] if len(set(found)) == 1 else None


# --- Cached model calls ---
class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}
        self.lock = threading.Lock()  # pmap threads insert and save concurrently

    def get(self, key_parts, compute):
        key = hashlib.sha256(json.dumps(key_parts, ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            if key in self.data:
                return self.data[key]
        value = compute()  # outside the lock so model calls still run in parallel
        with self.lock:
            self.data[key] = value
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        return value


def ask_jev(cache: Cache, ask, state: dict) -> dict:
    questions = {"route": ROUTE, **RULE_QUESTIONS}
    return cache.get(["jev", state, repr(questions)], lambda: ask(state, questions))


def ask_claude(cache: Cache, arm: str, case_input: str) -> str:
    def run():
        result = subprocess.run(
            [
                "claude", "-p", "--model", CLAUDE_MODEL, "--tools", "", "--setting-sources", "",
                "--strict-mcp-config", "--no-session-persistence",
                "--system-prompt", CLAUDE_SYSTEM, case_input,
            ],
            capture_output=True, text=True, timeout=300, cwd=gettempdir(),
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude -p failed: {result.stderr.strip()}")
        return result.stdout.strip()

    # `arm` is in the key so claude and claude_rep sample independently
    return cache.get(["claude", arm, CLAUDE_MODEL, CLAUDE_SYSTEM, case_input], run)


def claude_input(case: dict) -> str:
    return json.dumps({"request": case["prompt"], "recent_context": case["context"]}, ensure_ascii=False)


# --- Scoring ---
def accuracy(rows, arm, subset=lambda r: True):
    picked = [r for r in rows if subset(r)]
    hits = sum(r[arm] == r["gold"] for r in picked)
    return f"{hits}/{len(picked)} ({hits / len(picked):.0%})" if picked else "-"


def flips(rows, before, after):
    fixed = [r["id"] for r in rows if r[before] != r["gold"] and r[after] == r["gold"]]
    broken = [r["id"] for r in rows if r[before] == r["gold"] and r[after] != r["gold"]]
    return fixed, broken


def run(cases, independent, ask, raw_contexts=None):
    raw_contexts = raw_contexts or {}
    cache = Cache(HERE / "cache.json")

    def one(case):
        full = ask_jev(cache, ask, {"request": case["prompt"], "recent_context": case["context"]})
        bare = ask_jev(cache, ask, {"request": case["prompt"], "recent_context": ""})
        text = claude_input(case)
        clear = independent.get(case["id"]) == (case["gold"], False)
        outputs = {
            "claude": ask_claude(cache, "claude", text),
            "claude_rep": ask_claude(cache, "claude_rep", text),
            "claude_jev": ask_claude(cache, "claude_jev", text + suggestion_block(full["route"])),
        }
        wrong = None
        if clear:
            # harm test: a confident suggestion that is wrong, as the cookbook's failure mode
            wrong = plausible_wrong(full["route"]["probabilities"], case["gold"])
            block = suggestion_block({"choice": wrong, "confidence": 1.0})
            outputs["claude_wrong"] = ask_claude(cache, "claude_wrong", text + block)
        raw = None
        if case["id"] in raw_contexts:
            raw = ask_jev(cache, ask, {"request": case["prompt"], "recent_context": raw_contexts[case["id"]]})
        return {
            "id": case["id"],
            "gold": case["gold"],
            "rule": case["rule"],
            "needs_context": case["needs_context"],
            # clear = the independent annotator picked the same label and did not flag it ambiguous
            "clear": clear,
            "wrong_suggestion": wrong,
            "claude_wrong": None,
            "jev": full["route"]["choice"],
            "jev_confidence": full["route"]["confidence"],
            "jev_prompt": bare["route"]["choice"],
            "jev_rules": compose_rules(
                {k: full[k] for k in RULE_QUESTIONS}, fallback=full["route"]["choice"]
            ),
            "nouls": {k: round(full[k], 3) for k in RULE_QUESTIONS},
            # same questions, but recent_context is a raw transcript tail instead of a summary
            "jev_raw": raw and raw["route"]["choice"],
            "jev_raw_confidence": raw and raw["route"]["confidence"],
            "jev_raw_rules": raw and compose_rules({k: raw[k] for k in RULE_QUESTIONS}, raw["route"]["choice"]),
            **{arm: parse_label(out) for arm, out in outputs.items()},
            "raw": outputs,
        }

    return jev.pmap(one, cases)


def report(rows) -> str:
    arms = ["jev", "jev_prompt", "jev_rules", "claude", "claude_rep", "claude_jev"]
    subsets = {
        "all": lambda r: True,
        "clear": lambda r: r["clear"],
        "clear+needs_context": lambda r: r["clear"] and r["needs_context"],
        "clear+no_context": lambda r: r["clear"] and not r["needs_context"],
    }
    lines = ["| arm | " + " | ".join(subsets) + " |", "|---" * (len(subsets) + 1) + "|"]
    for arm in arms:
        lines.append(f"| {arm} | " + " | ".join(accuracy(rows, arm, s) for s in subsets.values()) + " |")

    clear = [r for r in rows if r["clear"]]
    lines += ["", "Jev confidence gate (clear cases): threshold -> coverage, accuracy of covered"]
    for t in [0.0, 0.3, 0.5, 0.7, 0.9]:
        covered = [r for r in clear if r["jev_confidence"] >= t]
        acc = sum(r["jev"] == r["gold"] for r in covered) / len(covered) if covered else 0
        lines.append(f"  >= {t:.1f}: {len(covered)}/{len(clear)} covered, {acc:.0%} correct")

    for before, after in [("claude", "claude_rep"), ("claude", "claude_jev"), ("claude", "claude_wrong")]:
        fixed, broken = flips(clear, before, after)
        lines.append(f"\n{before} -> {after} (clear): fixed {len(fixed)} {fixed}, broken {len(broken)} {broken}")

    for arm in ["jev", "claude"]:
        confusion = Counter((r["gold"], r[arm]) for r in clear if r[arm] != r["gold"])
        lines.append(f"\n{arm} errors (gold -> picked): " + ", ".join(f"{g}->{p} x{n}" for (g, p), n in confusion.most_common()))
    with_raw = [r for r in rows if r["jev_raw"] is not None]
    if with_raw:
        lines += ["", f"Raw transcript context ({len(with_raw)} context-dependent cases)", "",
                  "| arm | all | clear |", "|---|---|---|"]
        for arm in ["jev", "jev_raw", "jev_raw_rules", "jev_prompt"]:
            lines.append(f"| {arm} | {accuracy(with_raw, arm)} | {accuracy(with_raw, arm, lambda r: r['clear'])} |")
        lines.append("\njev_raw per case (gold -> picked, confidence summary -> raw):")
        for r in with_raw:
            mark = "ok " if r["jev_raw"] == r["gold"] else "ERR"
            lines.append(f"  {mark} {r['id']}: {r['gold']} -> {r['jev_raw']}  "
                         f"({r['jev_confidence']:.2f} -> {r['jev_raw_confidence']:.2f})")
    unparsed = [(r["id"], a) for r in rows for a in ["claude", "claude_rep", "claude_jev"] if r[a] is None]
    unparsed += [(r["id"], "claude_wrong") for r in clear if r["claude_wrong"] is None]
    if unparsed:
        lines.append(f"\nunparsed claude outputs: {unparsed}")
    return "\n".join(lines)


def main():
    cases = json.loads((HERE / "cases.json").read_text())
    independent = {
        x["id"]: (x["label"], x["ambiguous"]) for x in json.loads((HERE / "labels_independent.json").read_text())
    }
    raw_path = HERE / "raw_contexts.json"
    raw_contexts = json.loads(raw_path.read_text()) if raw_path.exists() else {}
    rows = run(cases, independent, jev.make_ask(), raw_contexts)
    (HERE / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    text = report(rows)
    (HERE / "report.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    sys.exit(main())
