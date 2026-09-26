# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`jev` is a CLI that lets a coding agent hand narrow judgments (find / rank / memgate / claims / screen) to TypeSafe's Jev model via `typesafe-sdk`. Every subcommand prints exactly one JSON object on stdout; errors go to stderr as `jev: <message>` with exit code 1. The whole tool is the single module `jev.py`.

The primary consumer is the "Jev delegation" section of `~/.claude/CLAUDE.md`, which documents the commands and relies on the output fields `uncertain`, `review`, `verdict` (including `uncertain`, `conflict`, `fabricated`) and on exit code 1. If you change a command's flags or output shape, update that section too.

## Commands

The CLI is installed as an **editable** pipx package (`pipx install --editable ~/AI/jev`, with `pytest` injected into the same venv), so edits to `jev.py` take effect in the `jev` command immediately. pytest is not on PATH; use the venv's copy:

```bash
PYTEST=~/.local/pipx/venvs/jev/bin/pytest

$PYTEST tests/test_jev.py                              # offline tests, fake model (fast)
$PYTEST tests/test_jev.py::test_memgate_verdict        # single test
$PYTEST tests/test_jev.py -k screen                    # by keyword
JEV_LIVE=1 $PYTEST tests/test_live.py                  # real API; skipped unless JEV_LIVE=1 and TYPESAFE_API_KEY are set
```

Live tests call the paid API (one request per `ask`) and assert on real model scores. Run them only after changing a question or threshold, and ask the user first. There is no linter or formatter configured.

## Architecture

- **Tuning lives at the top of `jev.py`**: thresholds (`UNSURE_BAND`, `FIND_*`, `DUPLICATE_MIN`, `CONFLICT_MIN`, `SCREEN`), request sizing (`CHUNK_*`, `PASSAGE_CHARS`, …), and every `Noul`/`Choice` question. Each subcommand section is labelled with the TypeSafe cookbook it follows. Redesign questions/thresholds with the `typesafe:typesafe-ai` skill, not ad hoc.
- **One model seam**: `make_ask()` returns `ask(state, questions) -> {id: float | {"choice", "probabilities", "confidence"}}` (Noul → float, Choice → dict). `main(argv, ask=None)` accepts an injected `ask`; `tests/test_jev.py` drives the full CLI through `main` with a recording fake (`fake(respond)`), so no test in that file touches the network.
- **Subcommands** are `cmd_<name>(args, ask) -> dict`, registered in `build_parser()` via `set_defaults(run=...)`. Raise `JevError` for user-facing failures; `main` turns `JevError`/`TypeSafeError`/`OSError` into exit 1.
- **Parallelism**: `pmap` fans requests out over a thread pool (`WORKERS`), so `ask` call order is nondeterministic. Tests match recorded calls by content, never by index.
- **All file input goes through `read_text`**, which refuses likely-secret filenames (`SECRET_NAME`) because content is sent to an external API. New file-reading paths must use it.

## Design constraints (learned the hard way)

- **One request per compared pair.** Do not pack several candidates/entries into one state and ask indexed questions: with 10 memory entries in one request, a near-verbatim duplicate in the last slot scored ~0.10 and scores leaked to neighbours. `rank`, `memgate` (duplicate/conflict), `claims` and `screen` all issue one request per item; `tests/fixtures/memgate_long_list.json` + `test_memgate_finds_duplicate_at_the_end_of_a_long_list` guard this.
- **Request limits**: Jev allows 32k tokens for state + longest question and 255 `Choice` options. Char caps are conservative because Korean can be ~1 token/char; `find` chunks by both line count and chars to stay under both.
- **`find`**: `Choice` probabilities sum to 1 within every chunk, so line scores are weighted by that chunk's `exists` noul; otherwise a chunk without the answer would still produce a confident line.
- **`memgate`**: verdict precedence is `conflict` > `duplicate` > `skip` > `uncertain` > `record` (a conflict means a stored record may be stale, so it outranks everything). `--existing` is parsed from `cross-memory query` numbered output by `parse_numbered`.
- **`claims`**: the quote is located by deterministic normalized string match first; an unmatched quote is `fabricated` without any model call.
- **`screen`**: paragraphs are never merged (an injected paragraph would drag clean ones down), and an excluded `prompt_injection` passage is reported without its text or preview.

## Environment

`.claude/settings.local.json` points `CROSS_MEMORY_DIR` at this project's own store (`…/memory-store/jev/memory`), so `cross-memory` records made in this repo land there.
