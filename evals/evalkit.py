"""Shared kit for the offline evals: a JSON-file cache for paid model calls, an isolated
`claude -p` call, and the scoring helpers both harnesses use."""

import hashlib
import json
import subprocess
import threading
from pathlib import Path
from tempfile import gettempdir


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


def run_claude(system: str, text: str, model: str, json_output: bool = False):
    """One `claude -p` call isolated from user settings, hooks, MCP servers and tools, run
    from a neutral cwd so no project CLAUDE.md is picked up.

    Returns the stripped reply, or with json_output the reply plus its usage and cost."""
    command = [
        "claude", "-p", "--model", model, "--tools", "", "--setting-sources", "",
        "--strict-mcp-config", "--no-session-persistence",
    ]
    if json_output:
        command += ["--output-format", "json"]
    command += ["--system-prompt", system, text]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300, cwd=gettempdir())
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr.strip()}")
    if not json_output:
        return result.stdout.strip()
    data = json.loads(result.stdout)
    if data.get("is_error"):
        # raise rather than return, so an error message is never cached as an answer
        raise RuntimeError(f"claude -p failed: {data.get('result')}")
    usage = data.get("usage") or {}
    return {
        "text": data["result"].strip(),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
        "cost_usd": data["total_cost_usd"],
        "duration_ms": data["duration_ms"],
    }


def accuracy(rows, arm, subset=lambda r: True, gold="gold"):
    picked = [r for r in rows if subset(r)]
    hits = sum(r[arm] == r[gold] for r in picked)
    return f"{hits}/{len(picked)} ({hits / len(picked):.0%})" if picked else "-"


def flips(rows, before, after, gold="gold"):
    fixed = [r["id"] for r in rows if r[before] != r[gold] and r[after] == r[gold]]
    broken = [r["id"] for r in rows if r[before] == r[gold] and r[after] != r[gold]]
    return fixed, broken
