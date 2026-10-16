# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`jev` is a CLI that lets a coding agent hand narrow judgments (find / rank / memgate / screen / search / which / locate) to TypeSafe's Jev model via `typesafe-sdk`. Every subcommand prints exactly one JSON object on stdout; errors go to stderr as `jev: <message>` with exit code 1. The whole tool is the single module `jev.py`.

The primary consumer is the "Jev delegation" section of `~/.claude/CLAUDE.md`, which documents the commands and relies on exit code 1 and on these output fields: `uncertain`, `no_match`, `verdict` (including `partial`, `absent`, and `ok`/`unverified` from `locate`), `click_px` and the `prompt_injection` reason. It no longer uses `claims` or `memgate` (evals showed Claude as accurate on inputs it already holds); both stay in the CLI. If you change a command's flags or output shape, update that section too.

## Commands

The CLI is installed as an **editable** pipx package (`pipx install --editable ~/AI/jev`, with `pytest` injected into the same venv), so edits to `jev.py` take effect in the `jev` command immediately. pytest is not on PATH; use the venv's copy:

```bash
PYTEST=~/.local/pipx/venvs/jev/bin/pytest

$PYTEST tests/test_jev.py                              # offline tests, fake model (fast)
$PYTEST tests/test_jev.py::test_memgate_verdict        # single test
$PYTEST tests/test_jev.py -k screen                    # by keyword
JEV_LIVE=1 $PYTEST tests/test_live.py                  # real API; skipped unless JEV_LIVE=1 and TYPESAFE_API_KEY are set
```

`evals/` holds offline experiments, not part of the CLI; in each, `report.md` holds the generated numbers and `findings.md` the design and interpretation. `evals/evalkit.py` is their shared kit: the JSON-file `Cache` for paid model calls, `run_claude` (an isolated `claude -p` call, optionally with token and cost usage via `--output-format json`) and the `accuracy`/`flips` scorers. `evals/route/` measures whether Jev can route tasks per the global CLAUDE.md Orchestration rules; its `cases.json` and `raw_contexts.json` are synthetic, with no real session content. `evals/vision/` measures `which` and `locate` on 8 synthetic screens that Playwright renders with the system Chrome (`playwright` is injected into the jev venv; no browser download); DOM boxes are the ground truth, and `findings.md` records why zoom crops were dropped and the marker check kept. `evals/judge/` compares Jev's claims and memgate judgments with Claude judging the same inputs (through the real `check_claim` / `cmd_memgate` paths); unlike route's synthetic cases, its memgate cases are built from the real cross-memory store (each `existing` list is frozen `cross-memory query` output; records are real past runs or synthetic ones written against it) and were scanned for PII. Harness tests run with `$PYTEST evals/route/test_eval_route.py evals/judge/test_eval_judge.py` and, from `evals/vision/`, `$PYTEST test_eval_vision.py`; `eval_vision.py` imports its image sizing, questions and marker from `jev`, so a change there invalidates its cache; `eval_route.py` and `eval_judge.py` make live Jev and `claude -p` calls unless they are in their `cache.json`, and both caches hold paid results, so keep their key construction unchanged (for judge that includes jev's questions, which the cached keys and the Claude prompts are built from).

Live tests call the paid API (one request per `ask`) and assert on real model scores. Run them only after changing a question or threshold, and ask the user first. There is no linter or formatter configured.

## Architecture

- **Tuning lives at the top of `jev.py`**: thresholds (`UNSURE_BAND`, `FIND_*`, `DUPLICATE_MIN`, `CONFLICT_MIN`, `SCREEN`, `SEARCH`, `LOCATE`), request sizing (`CHUNK_*`, `PASSAGE_CHARS`, `SEARCH_*`, `UNIT_*`, `IMAGE_*`, …), the pinned `VISION_MODEL`, and every `Noul`/`Choice`/`Box` question. Each model subcommand's section is labelled with the TypeSafe cookbook it follows. Redesign questions/thresholds with the `typesafe:typesafe-ai` skill, not ad hoc.
- **One model seam**: `make_ask()` returns `ask(state, questions) -> {id: float | {"choice", "probabilities", "confidence"} | {"left", "top", "right", "bottom", "confidence"}}` (Noul → float, Choice → dict, Box → dict). A state holding an `Image` is sent to `VISION_MODEL` (pinned `jev-1.14.0`, the model the vision eval measured) with the `TypeSafe-Danger-Zone-Images` header; other requests keep following `jev-latest`. `main(argv, ask=None)` accepts an injected `ask`; `tests/test_jev.py` drives the full CLI through `main` with a recording fake (`fake(respond)`), so no test in that file touches the network.
- **Subcommands** are `cmd_<name>(args, ask) -> dict`, registered in `build_parser()` via `set_defaults(run=...)`. Raise `JevError` for user-facing failures; `main` turns `JevError`/`TypeSafeError`/`OSError` into exit 1.
- **Parallelism**: `pmap` fans requests out over a thread pool (`WORKERS`), so `ask` call order is nondeterministic. Tests match recorded calls by content, never by index.
- **All file input goes through `read_text`** (text) or `load_image` (screenshots). Both refuse likely-secret filenames (`SECRET_NAME`) because content is sent to an external API. New file-reading paths must use one of them. Neither can see what an image shows, so the global CLAUDE.md limits images to screens the session rendered from fixture or dev data.

## Design constraints (learned the hard way)

- **One request per compared pair.** Do not pack several candidates/entries into one state and ask indexed questions: with 10 memory entries in one request, a near-verbatim duplicate in the last slot scored ~0.10 and scores leaked to neighbours. `rank`, `memgate` (duplicate/conflict) and `screen` all issue one request per item; `tests/fixtures/memgate_long_list.json` + `test_memgate_finds_duplicate_at_the_end_of_a_long_list` guard this.
- **Request limits**: Jev allows 32k tokens for state + longest question and 255 `Choice` options. Char caps are conservative because Korean can be ~1 token/char; `find` chunks by both line count and chars to stay under both.
- **`find`**: `Choice` probabilities sum to 1 within every chunk, so line scores are weighted by that chunk's `exists` noul; otherwise a chunk without the answer would still produce a confident line.
- **`memgate`**: verdict precedence is `conflict` > `duplicate` > `skip` > `uncertain` > `record` (a conflict means a stored record may be stale, so it outranks everything). `--existing` is parsed from `cross-memory query` numbered output by `parse_numbered`.
- **`screen`**: paragraphs are never merged (an injected paragraph would drag clean ones down), and an excluded `prompt_injection` passage is reported without its text or preview.
- **`search`**: walks directory → file → source unit with one request per item. Navigation thresholds are lenient (`dir_min` 0.5 < `file_min`/`unit_min` 0.6) because pruning a directory loses everything below it. The inventory skips secret-named files and counts them in `stats.skipped_secret` instead of raising, because `read_text` raising would abort the whole search; its binary sniff is a local raw read, and content sent to Jev still goes through `read_text`. Requests are capped by `SEARCH_MAX_REQUESTS` (directories also by `SEARCH_NAV_REQUESTS`, files by `SEARCH_FILE_REQUESTS` so source units keep part of the budget); items cut by the budget are listed in `unexplored` and set `complete` to false. Chunks respect both `UNIT_LINES` and `UNIT_CHARS`, like `find`.

- **Images** (Danger Zone: the format and accuracy can change between releases; re-run `evals/vision` and the live tests on each Jev release): `load_image` resizes to 280..1568 px per side and re-encodes PNG; an aspect ratio that cannot fit (a full-page capture) raises `JevError`. `which` is `rank` for screenshots (shared `ranked_result`, one request per image). `locate` asks presence + Box in one request, then draws a marker at the box center on the same resized image and asks whether it sits on the target. Do not trust Box confidence or replace the marker with a zoom crop: in `evals/vision` neither separated wrong boxes, while the marker check flagged 5/5.

## Environment

`.claude/settings.local.json` points `CROSS_MEMORY_DIR` at this project's own store (`…/memory-store/jev/memory`), so `cross-memory` records made in this repo land there.
