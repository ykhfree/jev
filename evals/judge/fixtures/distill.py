"""Phase 3: distill generalized project rules from run history via the claude CLI.

Flow: build_prompt -> run_claude -> proposed.md -> (human review) -> approve.
Proposed rules never reach rules.md without an explicit `approve` step.
"""

import json
import subprocess
from collections.abc import Callable
from datetime import datetime

from . import CrossMemoryError
from .store import MemoryStore

DETAILS_LIMIT = 2000  # chars of failure details included per run in the prompt
CLAUDE_TIMEOUT = 300  # seconds

PROMPT_TEMPLATE = """\
You are analyzing the run history of an automated coding agent to extract
durable, generalizable project rules.

Past run records (JSON; failures include a "details" field):
<records>
{records_json}
</records>

Existing approved rules (do NOT repeat these):
<rules>
{rules_md}
</rules>

Extract up to 10 NEW rules that would prevent past failures or repeat past
successes. Each rule must be generalizable (not tied to one run), actionable,
and imperative ("Always X", "Never Y", "Prefer Z").
Output ONLY a markdown bullet list, one "- rule" per line, no preamble,
no headings. If there is nothing new to extract, output exactly: NO_NEW_RULES
"""


def build_prompt(store: MemoryStore) -> str:
    """Serialize all runs (failures with truncated details) plus current rules."""
    records = []
    for entry in store.load_index():
        record = store.load_run(entry["id"])
        if record is None:
            continue
        if record.get("outcome") == "failure":
            details = store.load_failure_details(entry["id"])
            if details:
                record["details"] = details[:DETAILS_LIMIT]
        records.append(record)
    if not records:
        raise CrossMemoryError("no runs to distill; record some runs first")
    return PROMPT_TEMPLATE.format(
        records_json=json.dumps(records, ensure_ascii=False, indent=1),
        rules_md=store.load_rules() or "(none)",
    )


def run_claude(prompt: str, claude_cmd: str = "claude") -> str:
    """Invoke the claude CLI in headless print mode; the prompt goes via stdin."""
    try:
        proc = subprocess.run([claude_cmd, "-p"], input=prompt,
                              capture_output=True, text=True, timeout=CLAUDE_TIMEOUT)
    except FileNotFoundError:
        raise CrossMemoryError(
            f"claude CLI not found ({claude_cmd!r}); install it or pass --claude-cmd")
    except subprocess.TimeoutExpired:
        raise CrossMemoryError(f"claude CLI timed out after {CLAUDE_TIMEOUT}s")
    if proc.returncode != 0:
        raise CrossMemoryError(f"claude CLI failed: {proc.stderr.strip()}")
    return proc.stdout


def extract_bullets(text: str) -> list[str]:
    """Keep only '- rule' lines; tolerates preamble or NO_NEW_RULES responses."""
    return [line.rstrip() for line in text.splitlines() if line.startswith("- ")]


def distill(store: MemoryStore, runner: Callable[[str], str] = run_claude,
            *, now: datetime | None = None) -> list[str]:
    """Propose new rules into proposed.md; returns the bullets ([] if none)."""
    if store.proposed_path.exists():
        raise CrossMemoryError(
            "distilled/proposed.md has pending rules; "
            "run `cross-memory approve` or delete it first")
    bullets = extract_bullets(runner(build_prompt(store)))
    if not bullets:
        return []
    now = now or datetime.now().astimezone()
    header = (f"# Proposed rules — generated {now:%Y-%m-%d}\n"
              "# Review: delete any bad lines, then run `cross-memory approve`.\n\n")
    store.distilled_dir.mkdir(parents=True, exist_ok=True)
    store.proposed_path.write_text(header + "\n".join(bullets) + "\n", encoding="utf-8")
    return bullets


def approve(store: MemoryStore) -> tuple[int, int]:
    """Merge reviewed proposed.md into rules.md; returns (merged, duplicates)."""
    if not store.proposed_path.exists():
        raise CrossMemoryError("nothing to approve: distilled/proposed.md does not exist")
    bullets = extract_bullets(store.proposed_path.read_text(encoding="utf-8"))
    rules_text = store.load_rules()
    existing_lines = set(rules_text.splitlines())
    new = [b for b in bullets if b not in existing_lines]
    if new:
        if not rules_text:
            rules_text = "# Project rules\n"
        elif not rules_text.endswith("\n"):
            rules_text += "\n"
        store.distilled_dir.mkdir(parents=True, exist_ok=True)
        store.rules_path.write_text(rules_text + "\n".join(new) + "\n", encoding="utf-8")
    store.proposed_path.unlink()
    return len(new), len(bullets) - len(new)
