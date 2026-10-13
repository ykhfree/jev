"""Auto-sync the memory directory to git after a write.

Gated behind CROSS_MEMORY_AUTOSYNC so tests and offline use stay unaffected.
Every git failure is non-fatal: a `record` must still succeed when the memory
dir is not in a repo, git is missing, the network is down, or the push is
rejected. We commit locally whenever we can and only warn on a failed push.
"""

import os
import subprocess
import sys
from pathlib import Path

AUTOSYNC_ENV = "CROSS_MEMORY_AUTOSYNC"
PUSH_TIMEOUT = 30  # seconds; a hung remote must never block recording

# Values that mean "off" even though the variable is set.
_FALSEY = {"", "0", "false", "no", "off"}


def autosync_enabled(default: bool = False) -> bool:
    """Resolve auto-sync from the environment, falling back to *default*."""
    value = os.environ.get(AUTOSYNC_ENV)
    if value is None:
        return default
    return value.strip().lower() not in _FALSEY


def sync_to_git(memory_dir: str | Path, message: str) -> None:
    """Commit new/changed files under memory_dir and push. Never raises.

    `git add`/`commit` are scoped to memory_dir so unrelated working-tree
    changes (e.g. source edits in this same repo) are never swept in.
    """
    memory_dir = Path(memory_dir).expanduser().resolve()
    root = _repo_root(memory_dir)
    if root is None:
        _warn(f"{memory_dir} is not inside a git repository; skipping auto-sync")
        return

    path = str(memory_dir)
    added = _git(root, "add", "--", path)
    if added is None:
        return
    if added.returncode != 0:
        _warn(f"git add failed; skipping auto-sync: {_stderr(added)}")
        return
    staged = _git(root, "diff", "--cached", "--quiet", "--", path)
    if staged is None or staged.returncode == 0:
        return  # git unavailable, or nothing new staged under memory_dir

    commit = _git(root, "commit", "-m", message, "--", path)
    if commit is None or commit.returncode != 0:
        _warn(f"git commit failed; skipping push: {_stderr(commit)}")
        return

    push = _git(root, "push", timeout=PUSH_TIMEOUT)
    if push is None or push.returncode != 0:
        _warn(f"committed locally but push failed: {_stderr(push)}")


def _repo_root(memory_dir: Path) -> Path | None:
    """Top-level dir of the repo containing memory_dir, or None if there is none."""
    proc = _git(memory_dir, "rev-parse", "--show-toplevel")
    if proc is None or proc.returncode != 0:
        return None
    return Path(proc.stdout.strip())


def _git(cwd: Path, *args: str,
         timeout: int | None = None) -> subprocess.CompletedProcess | None:
    """Run `git -C <cwd> <args>`; None if git is missing or the call times out."""
    try:
        return subprocess.run(["git", "-C", str(cwd), *args],
                              capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        _warn("git executable not found; skipping auto-sync")
    except subprocess.TimeoutExpired:
        _warn(f"git {args[0]} timed out after {timeout}s; skipping auto-sync")
    return None


def _stderr(proc: subprocess.CompletedProcess | None) -> str:
    return (proc.stderr if proc else "").strip()


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)
