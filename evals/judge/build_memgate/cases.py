"""Case definitions; writes ~/AI/jev/evals/judge/memgate_cases.json."""
import json
from pathlib import Path

from build import AUDIT, LIVE_ROOT, PRE_AUDIT, frozen, run_at, snapshot

OUT = Path.home() / "AI/jev/evals/judge/memgate_cases.json"
PRIVACY = {"YKH_S_API": "LLM_API_KEY"}  # env var name carrying the owner's initials

cases = []
_snaps = {}


def snap(cutoff):
    if cutoff not in _snaps:
        _snaps[cutoff] = snapshot(PRE_AUDIT, cutoff)
    return _snaps[cutoff]


def add(gold, source, rec, note, *, target=None, root=LIVE_ROOT, store="ai", query_task=None, drop=()):
    existing, head, substituted = frozen(query_task or rec["task"], root, store, target, drop)
    if target and head is None:
        raise SystemExit(f"target missing: {target}")
    cases.append({
        "id": f"m{len(cases) + 1:02d}",
        "gold": gold,
        "source": source,
        "target": head,
        "task": rec["task"],
        "outcome": rec["outcome"],
        "result": rec["result"],
        "learnings": rec["learnings"],
        "existing": existing,
        "note": note,
        "_substituted": substituted,
    })


def stored(commit, store, run_id):
    r = run_at(commit, store, run_id)
    return {k: r[k] for k in ("task", "outcome", "result", "learnings")}, r["timestamp"]


def syn(task, result, learnings, outcome="success"):
    return {"task": task, "outcome": outcome, "result": result, "learnings": learnings}


# ---------------------------------------------------------------- real_audit
# Candidate = the record as written; existing = query over a snapshot of the stores at the
# pre-audit import (914cd27) holding only runs older than the candidate.

rec, ts = stored(PRE_AUDIT, "trading-bot", "2026-06-11_1451")
add("record", "real_audit", rec,
    "Overlaps 1432 on 'OUTCOME prompt beats feature-augmented prompts' but adds the cross-symbol (ETH) holdout rule and "
    "the byte-identical BASE prompt / SHA-256 cache rule; the audit merged 1432 into this one, so this is the keeper",
    root=snap(ts), store="trading-bot")

rec, ts = stored(PRE_AUDIT, "trading-bot", "2026-06-11_1613")
add("record", "real_audit", rec,
    "New root cause (intrabar OFF counts straddle bars as losses) and a durable 'always run with intrabar ON' rule; "
    "no earlier entry covers it; the audit kept its learnings in a re-record",
    root=snap(ts), store="trading-bot")

rec, ts = stored(PRE_AUDIT, "trading-bot", "2026-06-14_2225")
add("record", "real_audit", rec,
    "Distill plan with reusable design rules (fit on outcomes not LLM scores, train/serve skew, re-pick threshold per "
    "score scale); nothing earlier says this; the audit kept it unchanged",
    root=snap(ts), store="trading-bot")

rec, ts = stored(PRE_AUDIT, "trading-bot", "2026-06-15_2328")
add("record", "real_audit", rec,
    "Near-duplicate of 2321 (compressed scores, ETH hurt, OOS fails) that adds the fitted factor weights, RR pruning "
    "rationale, gate verdict and LLM-vs-heuristic comparison; the audit merged 2321 into this one, not the reverse",
    root=snap(ts), store="trading-bot")

rec, ts = stored(PRE_AUDIT, "trading-bot", "2026-06-15_2356")
add("record", "real_audit", rec,
    "Complementary, not a conflict: 2328 says the heuristic fails cross-symbol; this narrows scope to BTC-only (in-sample) "
    "and itself says the BTC win is an in-sample illusion; adds the live-wiring pattern and symbol-scoping rule",
    root=snap(ts), store="trading-bot")

rec, ts = stored(PRE_AUDIT, "trading-bot", "2026-06-17_1557")
add("conflict", "real_audit", rec,
    "Fresh BTC re-score did NOT reproduce OUTCOME th0.65 (71.18%/+6.24% vs documented 74.1%/+7.83%), contradicting the "
    "stored claim that OUTCOME+0.65 passed BTC with exactly those numbers; the audit annotated this th0.65 conflict",
    target='"Implement heuristic-distill plan', root=snap(ts), store="trading-bot")

rec, ts = stored(PRE_AUDIT, "trading-bot-rust", "2026-07-04_2304")
add("record", "real_audit", rec,
    "Parity verification with a durable reusable pattern (3-way parallel agents given the list of intended differences) "
    "and the logback->logging.rs port note; nothing earlier covers them. Its '48 tests' doc remark vs the port run's "
    "'48 tests green' is a count that grew, not incompatible learnings",
    root=snap(ts), store="trading-bot-rust")

rec, ts = stored(PRE_AUDIT, "trading-bot-rust", "2026-07-04_2308")
add("duplicate", "real_audit", rec,
    "2304 already states the cause (fixed creation date but write_all goes through the real Utc::now()) and the fix "
    "(use write_at with a fixed time in tests); this learning only restates it as a general rule",
    target='포팅 패리티 검증', root=snap(ts), store="trading-bot-rust")

# Written during the audit: corrected re-record vs the pre-audit store that still holds the original.
rec, ts = stored(AUDIT, "trading-bot", "2026-09-26_2244_6")
add("conflict", "real_audit", rec,
    "The re-record says the filter lives in docs/swing_points_strategy_fakeout.pine and docs/swing_points_strategy.pine "
    "has no filter; the stored original says it was ported into docs/swing_points_strategy.pine",
    target='"Port HeuristicFakeoutFilterClient into docs/swing_points_strategy.pine"', root=snap(ts), store="trading-bot")

# Carved from 2304 learning 2: the audit (3a60d5b) dropped the '48 tests' doc remark as a stale TODO.
rec = {
    "task": "trading-bot-rust CLAUDE.md 테스트 개수 기술 확인",
    "outcome": "success",
    "result": "CLAUDE.md는 '48 tests'라고 적혀 있으나 실제로는 53개",
    "learnings": ["CLAUDE.md의 '48 tests' 기술은 로깅 테스트 5개 추가로 stale(현재 53개)"],
}
add("skip", "real_audit", rec,
    "A stale count in one doc at one moment: a to-do, not a learning; the audit dropped it (3a60d5b); existing is the "
    "current store, where 2304 no longer carries it",
    store="trading-bot-rust")

# ------------------------------------------------------------ deleted_replay
# Deleted runs replayed against the current (federated) store, as the memgate design work did.


def deleted(commit, store, run_id):
    return stored(commit + "^", store, run_id)[0]


add("conflict", "deleted_replay", deleted("7bc75da", "cross-memory-cli", "2026-09-25_2155"),
    "Says ssh to github.com is denied in Claude Code shells; the stored run reports the later state: push works after "
    "ssh-add --apple-use-keychain (upstream learning is also a duplicate, but conflict ranks first)",
    target='"Verify CROSS_MEMORY_AUTOSYNC push works on this Mac"', store="cross-memory-cli")

add("conflict", "deleted_replay", deleted("2470014", "req-shield", "2026-09-25_2200"),
    "Advises resolving the optional bean with @Qualifier ObjectProvider.getIfAvailable; the stored review says that call "
    "silently ignores a wrong-typed bean and to resolve by name instead; entry 1 (its re-record, 2133) also replaces that "
    "advice with a by-name lookup and repeats the other four learnings verbatim",
    target='"Review req-shield changes', store="req-shield")

add("duplicate", "deleted_replay", deleted("7d0d0e9", "req-shield", "2026-09-25_2259"),
    "Re-recorded as 2133_2: two of three learnings are verbatim there; the third (StaticListableBeanFactory ignores "
    "names) was judged not worth carrying",
    target='"Review req-shield changes', store="req-shield")

add("duplicate", "deleted_replay", deleted("82855f3", "req-shield", "2026-09-25_2330"),
    "Same task, result and learnings as the stored 2133_3 (near-verbatim; the fixture of the long-list regression)",
    target='"Fix req-shield review findings', store="req-shield")

add("record", "deleted_replay", deleted("575a8cb", "req-shield", "2026-09-26_0003"),
    "Durable archify CLI/layout learnings with no archify entry in any store; it was deleted for sitting in the "
    "req-shield store, which memgate cannot see", store="req-shield")

add("conflict", "deleted_replay", deleted("da407f7", "ai", "2026-09-26_1936"),
    "Blames the scratchpad location and says 'bash script.sh' is the fix; the stored run found the cause is the "
    "com.apple.quarantine xattr (even outside the sandbox) and that bash fails for scripts that exec other scripts",
    target='"prompt-audit of ~/.claude CLAUDE.md, agents, skillify; then applied the diff"')

add("conflict", "deleted_replay", deleted("37f5f32", "ai", "2026-09-27_1221"),
    "Says routing from a raw transcript tail is untested and the Noul router scored 69%; the stored later run tested "
    "it (21/21) and reports 48-69%",
    target='"Evaluate whether TypeSafe Jev can route')

add("duplicate", "deleted_replay", deleted("691fbb2", "ai", "2026-09-27_1307"),
    "Every learning appears verbatim in the stored 1314 run, which adds the harm test on top",
    target='"Evaluate whether TypeSafe Jev can route')

# ---------------------------------------------------------------- synthetic
# duplicates: reworded learnings of one specific stored entry
add("duplicate", "synthetic", syn(
    "req-shield: fix flaky coroutine thread-name assertion in Gradle tests",
    "Assertion now uses startsWith; 355 tests pass",
    ["With -ea (as in Gradle test runs) kotlinx.coroutines turns on debug mode and suffixes thread names with "
     "' @coroutine#N', so a thread-name equality check inside a coroutine fails; compare the prefix instead."]),
    "Reworded copy of the stored coroutine debug-mode thread-name learning in the req-shield pre-release run",
    target='"req-shield pre-release', store="req-shield")

add("duplicate", "synthetic", syn(
    "req-shield Spring AOP advice on void method does nothing with WebFlux adapter",
    "Reproduced with a probe; documented as a limitation",
    ["@Around 어드바이스가 lazy Mono를 반환하면 void(Unit) 메서드에서는 프록시가 반환값을 버리므로 아무도 구독하지 않고 "
     "대상 메서드 본문이 실행되지 않는다. Mono가 아닌 다른 반환 타입이면 호출자가 ClassCastException을 받는다."]),
    "Korean paraphrase of the stored English learning on @Around advice returning a lazy Mono",
    target='"req-shield: fix DST skew', store="req-shield")

add("duplicate", "synthetic", syn(
    "call TypeSafe jev from Claude Bash tool after adding API key to ~/.zshrc",
    "jev still reported the key missing until a new Claude Code session",
    ["The environment of Claude Code's Bash tool is captured once when the session starts, so a variable exported "
     "from a shell dotfile during the session is not seen until the next session; check it meanwhile with zsh -lc."],
    outcome="failure"),
    "Reworded copy of the stored 'Bash tool env is a snapshot taken at session start' learning",
    target='"build jev CLI and call TypeSafe API')

add("duplicate", "synthetic", syn(
    "cross-memory query misses autosync records: task keywords",
    "Re-recorded the task with plain keywords; query now finds it",
    ["cross-memory query only looks at the task text, and \\w+ tokenizing keeps an env var name such as "
     "CROSS_MEMORY_AUTOSYNC as one token, so a search for 'autosync' never hits it; use plain search words in tasks."]),
    "Reworded copy of the stored cross-memory-cli audit learning on task-only scoring and tokenization",
    target='"Audit cross-memory store records', store="cross-memory-cli")

add("duplicate", "synthetic", syn(
    "Re-check fakeout-filter win rate: backtest intrabar straddle handling",
    "Win rate rose once intrabar resolution was enabled",
    ["Backtests that resolve straddle bars (stop and TP inside one 1h candle) as a conservative loss, i.e. without "
     "intrabar data, understate both win rate and return; turn intrabar resolution on before trusting or comparing numbers."]),
    "Reworded copy of the stored 'always run backtests with intrabar/straddle resolution ON' learning",
    target="Investigate low win rate", store="trading-bot")

add("duplicate", "synthetic", syn(
    "req-shield core: executor rejection leaks lock in background cache refresh",
    "Caught the rejection at the call site",
    ["If the bounded executor is full or shut down, CompletableFuture.runAsync fails right away by throwing "
     "RejectedExecutionException on the calling thread, so the task's finally block never runs and its lock stays held; "
     "catch the exception where runAsync is called and unlock there."]),
    "Reworded copy of the stored CompletableFuture.runAsync rejection learning",
    target='"req-shield core: handle executor rejection', store="req-shield")

# conflicts: opposite fact / later state against one stored entry
add("conflict", "synthetic", syn(
    "Remeasure BTC 5yr LLM OUTCOME fakeout filter th0.65 after re-score",
    "Fresh re-score reproduced the documented th0.65 result (74.1% win, +7.83% cum)",
    ["LLM OUTCOME absolute scores are stable across re-scorings: a fresh 5yr BTC re-score gave the same th0.65 result, "
     "so the fixed 0.65 threshold is reproducible and needs no percentile/relative replacement."]),
    "Directly contradicts the stored remeasure record: score drift ~0.08-0.10 broke th0.65 reproducibility",
    target="Add MDD/Calmar metrics", store="trading-bot")

add("conflict", "synthetic", syn(
    "Verify cross-memory autosync git push on a fresh store repo",
    "record pushed to the new remote with no manual setup",
    ["cross-memory autosync now pushes with --set-upstream itself, so a new store repo needs no 'git push -u origin "
     "main' or push.autoSetupRemote before autosync works."]),
    "Later state that makes the stored 'autosync push needs the store repo branch to have an upstream' no longer true",
    target='"Verify CROSS_MEMORY_AUTOSYNC push works', store="cross-memory-cli")

# records: new durable learnings on topics next to stored entries
add("record", "synthetic", syn(
    "req-shield: make nowToEpochTime DST tests deterministic",
    "Injected java.time.Clock; DST overlap covered by a Clock.fixed test",
    ["To test epoch-time code across a DST fall-back overlap, inject a java.time.Clock and read Instant.now(clock) or "
     "clock.millis(); a hard-coded System.currentTimeMillis() cannot be pinned to the overlap hour in a unit test."]),
    "Next to the stored DST learning (use System.currentTimeMillis/Instant.now) but adds a new testing technique; "
    "compatible with it, not a conflict", store="req-shield")

add("record", "synthetic", syn(
    "Percentile threshold for LLM OUTCOME fakeout filter across re-scorings",
    "Blocking the top 8% of scores per scoring run gave the same blocked set within 3 trades on both re-scorings",
    ["A per-run percentile threshold on LLM OUTCOME scores survives score drift: across two re-scorings it blocked "
     "nearly the same trades, whereas the fixed th0.65 did not; set the filter by rank, not by absolute score."]),
    "Same subject as the stored drift record and agrees with its 'use a percentile threshold' advice, adding the "
    "measured result; complementary, not a duplicate or conflict", store="trading-bot")

add("record", "synthetic", syn(
    "jev find: Choice line scores in a chunk without the answer",
    "Weighted line probabilities by the chunk's exists Noul",
    ["Jev Choice probabilities always sum to 1 within one request, so a chunk that does not contain the answer still "
     "yields a confident top line; multiply line scores by a separate 'does the answer exist here' Noul."]),
    "New Jev question-design learning next to the stored one-pair-per-request learning; different mechanism")

add("record", "synthetic", syn(
    "Evaluate Jev vs claude -p: measure Claude arm cost per case",
    "Cost column added from the JSON output",
    ["claude -p --output-format json reports total_cost_usd per call; read it from there to compare the Claude arm's "
     "cost with Jev instead of estimating tokens."]),
    "New eval-harness fact next to the stored isolated claude -p flags learning; not covered there")

add("record", "synthetic", syn(
    "cross-memory query recall for Korean task text",
    "Korean records found once task words were written without particles",
    ["cross-memory query scores only the task field, and \\w+ keeps a Hangul word with its particle as one token "
     "('스코어링을' does not match '스코어링'), so write Korean task keywords bare, without particles."]),
    "Near-duplicate of the stored task-keyword learning that adds a genuinely new detail (Korean particles break matches)",
    store="cross-memory-cli")

# skips: one-off status, transient machine state, noise
add("skip", "synthetic", syn(
    "req-shield: bump version to 1.2.0 and run the full build",
    "Version bumped",
    ["355 tests, ktlint and jacoco all pass on the release branch."]),
    "Status report of one build; no reusable learning", store="req-shield")

add("skip", "synthetic", syn(
    "Push cross-memory store after recording",
    "One push failed this afternoon; a retry a minute later succeeded",
    ["The ~/.ssh/agent socket hung once this afternoon during a cross-memory push; the next push a minute later went through."],
    outcome="failure"),
    "Transient machine state from one afternoon; the durable SSH advice is already stored elsewhere",
    store="cross-memory-cli")

add("skip", "synthetic", syn(
    "Run BTC 3mo fakeout-filter backtest",
    "41 trades, 68.3% win, +2.1% cum",
    ["The 3mo BTC backtest today gave 41 trades at 68.3% win and +2.1% cumulative return."]),
    "One-off numbers with no rule or decision attached", store="trading-bot")

add("skip", "synthetic", syn(
    "fix typo in req-shield README",
    "Fixed 'recieve' in the WebFlux section",
    ["README WebFlux section had 'recieve' instead of 'receive'."]),
    "One-off typo fix", store="req-shield")

add("skip", "synthetic", syn(
    "run jev tests",
    "71 passed in 3.2s",
    ["All 71 jev tests pass."]),
    "Test run status only")

add("skip", "synthetic", syn(
    "Rebase trading-bot feature branch onto main",
    "Rebased; resolved 2 conflicts in FilterTuningRunner.kt",
    ["FilterTuningRunner.kt had 2 rebase conflicts, resolved by keeping both sides."]),
    "One-off merge chore", store="trading-bot")

add("skip", "synthetic", syn(
    "Export req-shield archify workflow diagram for the demo",
    "Exported PNG to the desktop",
    ["Saved the diagram as req-shield-flow.png on the desktop for tomorrow's demo."]),
    "One-off file location for a single event", store="req-shield")

add("skip", "synthetic", syn(
    "trading-bot fakeout-filter scoring run via genai-gateway",
    "Scoring paused 14:00-14:40 while the gateway was down, then resumed",
    ["genai-gateway was down for 40 minutes this afternoon."],
    outcome="failure"),
    "Outage on one day; next to the stored gateway rate-limit how-to but carries no durable rule", store="trading-bot")

add("skip", "synthetic", syn(
    "Fix req-shield review findings follow-up",
    "Done",
    ["Thorough testing pays off."]),
    "Generic platitude: no specific fact or decision", store="req-shield")


def scrub(obj):
    if isinstance(obj, str):
        for k, v in PRIVACY.items():
            obj = obj.replace(k, v)
        return obj.replace(str(Path.home()), "~")
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    return obj


cases = scrub(cases)
subs = [c["id"] for c in cases if c.pop("_substituted")]
OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")
print(len(cases), "cases; target substituted in:", subs)
