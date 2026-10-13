"""Phase 1: persistent storage of run records under a memory/ directory."""

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from . import CrossMemoryError

OUTCOMES = ("success", "failure")

# index.json keeps only the fields needed for searching; full records stay in runs/.
INDEX_FIELDS = ("id", "timestamp", "task", "outcome")


@dataclass
class RunRecord:
    """One loop-run result; serialized as runs/<YYYY-MM>/<id>.json."""

    id: str
    timestamp: str
    task: str
    outcome: str
    result: str
    learnings: list[str] = field(default_factory=list)


class MemoryStore:
    """Owns all paths and file I/O under a single memory/ directory."""

    def __init__(self, memory_dir: str | Path) -> None:
        # expanduser: paths like ~/cross-memory-store/foo come from env vars
        # or settings files where the shell never expands "~".
        self.memory_dir = Path(memory_dir).expanduser()
        self.runs_dir = self.memory_dir / "runs"
        self.failures_dir = self.memory_dir / "failures"
        self.distilled_dir = self.memory_dir / "distilled"
        self.index_path = self.memory_dir / "index.json"
        self.rules_path = self.distilled_dir / "rules.md"
        self.proposed_path = self.distilled_dir / "proposed.md"

    # -- recording (Phase 1) -------------------------------------------------

    def record_run(self, task: str, outcome: str, result: str,
                   learnings: list[str] | None = None, details: str | None = None,
                   *, now: datetime | None = None) -> RunRecord:
        """Persist one run; failures are additionally copied into failures/."""
        if outcome not in OUTCOMES:
            raise CrossMemoryError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")
        now = now or datetime.now().astimezone()
        record = RunRecord(
            id=self._next_id(now),
            timestamp=now.isoformat(timespec="seconds"),
            task=task,
            outcome=outcome,
            result=result,
            learnings=list(learnings or []),
        )
        run_path = self.run_path(record.id)
        run_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(run_path, asdict(record))
        if outcome == "failure":
            failure_path = self.failure_path(record.id)
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_json(failure_path, {**asdict(record), "details": details or ""})
        self._append_to_index(record)
        return record

    def delete_run(self, run_id: str) -> None:
        """Remove a run and its failure record (if any); updates the index.

        Raises CrossMemoryError if no such run exists.
        """
        run_path = self.run_path(run_id)
        if not run_path.exists():
            raise CrossMemoryError(f"no such run: {run_id!r}")
        run_path.unlink()
        failure_path = self.failure_path(run_id)
        if failure_path.exists():
            failure_path.unlink()
        entries = [entry for entry in self.load_index() if entry["id"] != run_id]
        self._save_index(entries)

    def run_path(self, run_id: str) -> Path:
        """runs/<YYYY-MM>/<id>.json — month derived from the id's date prefix."""
        return self.runs_dir / run_id[:7] / f"{run_id}.json"

    def failure_path(self, run_id: str) -> Path:
        """failures/<YYYY-MM>/<id>.json — month derived from the id's date prefix."""
        return self.failures_dir / run_id[:7] / f"{run_id}.json"

    def _next_id(self, now: datetime) -> str:
        """Minute-resolution id; same-minute collisions get a _2, _3, ... suffix."""
        base = now.strftime("%Y-%m-%d_%H%M")
        candidate, n = base, 1
        while self.run_path(candidate).exists():
            n += 1
            candidate = f"{base}_{n}"
        return candidate

    # -- loading ---------------------------------------------------------------

    def load_run(self, run_id: str) -> dict | None:
        """Return the run record dict, or None (warning on stderr) if unreadable."""
        return self._load_json_or_warn(self.run_path(run_id))

    def load_failure_details(self, run_id: str) -> str:
        """Return the failure 'details' text for a run, or '' if none recorded."""
        data = self._load_json_or_warn(self.failure_path(run_id))
        return (data or {}).get("details", "")

    def load_rules(self) -> str:
        """Return the approved rules.md content, or '' if it does not exist."""
        try:
            return self.rules_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    # -- index -----------------------------------------------------------------

    def load_index(self) -> list[dict]:
        """Return index entries, rebuilding from runs/ if missing or corrupt."""
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            return data["runs"]
        except (OSError, ValueError, KeyError, TypeError):
            return self.rebuild_index()

    def rebuild_index(self) -> list[dict]:
        """Rebuild index.json from runs/, skipping unreadable files."""
        entries = []
        if self.runs_dir.is_dir():
            # "**/*.json" finds runs in their month folders (and any legacy flat ones).
            for path in sorted(self.runs_dir.glob("**/*.json")):
                record = self._load_json_or_warn(path)
                if record is not None:
                    entries.append({key: record.get(key, "") for key in INDEX_FIELDS})
        if self.memory_dir.is_dir():
            self._save_index(entries)
        return entries

    def _append_to_index(self, record: RunRecord) -> None:
        entries = self.load_index()
        if not any(entry["id"] == record.id for entry in entries):
            entries.append({key: getattr(record, key) for key in INDEX_FIELDS})
        self._save_index(entries)

    def _save_index(self, entries: list[dict]) -> None:
        entries = sorted(entries, key=lambda entry: entry["id"])
        self._write_json(self.index_path, {"version": 1, "runs": entries})

    # -- helpers -----------------------------------------------------------------

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    @staticmethod
    def _load_json_or_warn(path: Path) -> dict | None:
        """Parse a JSON object file; None if missing, warn + None if unreadable."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            print(f"warning: skipping unreadable record {path}", file=sys.stderr)
            return None
        return data
