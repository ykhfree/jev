"""Offline tests for the judge eval harness: no Jev or Claude calls."""

import itertools
import json
import subprocess
import tempfile

import pytest

import eval_judge as ej
import evalkit  # importable once eval_judge has put evals/ on sys.path

USAGE = {"input_tokens": 10, "output_tokens": 2, "cache_read_tokens": 0, "cache_creation_tokens": 0,
         "cost_usd": 0.01, "duration_ms": 900}


def fake_ask(respond):
    """An ask(state, questions) stand-in that records its calls."""
    calls = []

    def ask(state, questions):
        calls.append((state, questions))
        return respond(state, questions)

    ask.calls = calls
    return ask


def fake_runner(reply):
    """A run_claude stand-in that records its calls. reply(system, text, n) gives the reply text,
    where n counts earlier calls with the same system and text."""
    calls = []

    def run(system, text, model, json_output=False):
        n = sum((s, t) == (system, text) for s, t, *_ in calls)
        calls.append((system, text, model, json_output))
        return {"text": reply(system, text, n), **USAGE}

    run.calls = calls
    return run


# --- label parsing and case selection ---


def test_parse_label_accepts_exactly_one_label():
    assert ej.parse_label("Supports.", ej.RELATIONS) == "supports"
    assert ej.parse_label("**says_nothing**\n", ej.RELATIONS) == "says_nothing"
    assert ej.parse_label("Skip. Verdict: skip", ej.MEMGATE_LABELS) == "skip"  # one label, said twice
    # two different labels, a near-miss spelling, or nothing: unparseable, never a guess
    assert ej.parse_label("duplicate, or maybe conflict", ej.MEMGATE_LABELS) is None
    assert ej.parse_label("supports, not contradicts", ej.RELATIONS) is None
    assert ej.parse_label("says nothing", ej.RELATIONS) is None
    assert ej.parse_label("recorded", ej.MEMGATE_LABELS) is None
    assert ej.parse_label("", ej.MEMGATE_LABELS) is None


def test_claim_verdict_maps_claude_relations_to_jev_verdicts():
    assert ej.claim_verdict("contradicts") == "contradicted"
    assert ej.claim_verdict("says_nothing") == "unsupported"
    assert ej.claim_verdict("supports or says_nothing") is None


@pytest.mark.parametrize(
    "label, clear",
    [
        ({"label_section": "unsupported", "label_file": "contradicted", "ambiguous": False}, True),
        ({"label_section": "unsupported", "label_file": "contradicted", "ambiguous": True}, False),
        ({"label_section": "unsupported", "label_file": "unsupported", "ambiguous": False}, False),
        (None, False),  # never annotated
    ],
)
def test_claims_case_is_clear_only_when_both_labels_match_gold_unambiguously(label, clear):
    assert ej.is_clear(label, {"label_section": "unsupported", "label_file": "contradicted"}) is clear


def test_memgate_case_is_clear_only_when_the_label_matches_gold():
    assert ej.is_clear({"label": "skip", "ambiguous": False}, {"label": "skip"}) is True
    assert ej.is_clear({"label": "record", "ambiguous": False}, {"label": "skip"}) is False


# --- tiers and the decision rule's counts ---


def claims_row(case_id, gold, jev, review, claude, clear=True, kind="value"):
    arms = ej.CLAUDE_ARMS["claims"]
    return {"id": case_id, "kind": kind, "gold_section": gold, "gold_file": gold, "clear": clear,
            "jev": jev, "jev_review": review, "jev_seconds": [0.3],
            **{a: claude for a in arms}, "raw": {a: claude or "maybe" for a in arms}, "usage": {a: USAGE for a in arms}}


def memgate_row(case_id, gold, jev, claude, seconds, clear=True):
    arms = ej.CLAUDE_ARMS["memgate"]
    return {"id": case_id, "gold": gold, "clear": clear, "jev": jev, "jev_seconds": seconds,
            **{a: claude for a in arms}, "raw": {a: claude or "maybe" for a in arms}, "usage": {a: USAGE for a in arms}}


def test_claims_tier_is_unreviewed_verified_or_contradicted_and_veto_counts_only_there():
    rows = [
        claims_row("ok", "verified", "verified", False, "verified"),
        claims_row("veto", "contradicted", "verified", False, "verified"),  # a false claim passed as true
        claims_row("reviewed", "contradicted", "verified", True, "verified"),  # same error, sent to review
        claims_row("caught", "contradicted", "contradicted", False, "verified"),
        claims_row("missed", "verified", "contradicted", False, "verified"),  # wrong, not the vetoed direction
        claims_row("silent", "unsupported", "unsupported", False, "verified"),  # autonomous, but no action defined
        claims_row("fab", "verified", "fabricated", False, "verified"),
    ]
    assert ej.ids(rows, ej.claims_autonomous) == ["ok", "veto", "caught", "missed"]
    assert ej.veto_errors(rows) == ["veto"]
    assert ej.unsupported_unreviewed(rows) == ["silent"]


def test_memgate_tier_and_learnings_lost():
    rows = [
        memgate_row("a", "record", "skip", "record", []),
        memgate_row("b", "record", "duplicate", "duplicate", []),
        memgate_row("c", "record", "uncertain", "conflict", []),  # not dropped: goes to review
        memgate_row("d", "skip", "skip", "skip", []),
        memgate_row("e", "record", "conflict", None, []),
    ]
    assert ej.ids(rows, ej.memgate_autonomous) == ["a", "b", "d"]
    assert ej.learnings_lost(rows, "jev") == ["a", "b"]
    assert ej.learnings_lost(rows, "claude") == ["b"]


# --- cached model calls ---


def test_cached_ask_calls_the_model_once_and_replays_its_time(tmp_path, monkeypatch):
    clock = itertools.count(10.0, 2.5)
    monkeypatch.setattr(ej.time, "perf_counter", lambda: next(clock))
    ask = fake_ask(lambda state, questions: {"relation": {"choice": "supports"}})
    questions = {"relation": ej.jev.RELATION_QUESTION}
    state = {"claim": "c", "section": "s"}
    seconds = []
    cached = ej.cached_ask(ej.Cache(tmp_path / "cache.json"), ask, seconds)

    assert cached(state, questions) == cached(state, questions) == {"relation": {"choice": "supports"}}
    assert len(ask.calls) == 1
    # the hit reports the original call's wall time, not the near-zero time of the hit
    assert seconds == [2.5, 2.5]
    cached({"claim": "other", "section": "s"}, questions)
    assert len(ask.calls) == 2
    # a later run reading the same cache file makes no call either
    later = []
    ej.cached_ask(ej.Cache(tmp_path / "cache.json"), ask, later)(state, questions)
    assert len(ask.calls) == 2 and later == [2.5]


def test_claude_arms_are_cached_apart_so_a_repeat_is_a_new_sample(tmp_path, monkeypatch):
    runner = fake_runner(lambda system, text, n: ["supports", "contradicts"][n])
    monkeypatch.setattr(ej, "run_claude", runner)
    cache = ej.Cache(tmp_path / "cache.json")

    first = ej.ask_claude(cache, "claude_file", "sys", "input")
    rep = ej.ask_claude(cache, "claude_rep", "sys", "input")
    assert (first["text"], rep["text"]) == ("supports", "contradicts")
    assert len(cache.data) == 2
    # the same arm again is served from the cache
    assert ej.ask_claude(cache, "claude_file", "sys", "input")["text"] == "supports"
    assert len(runner.calls) == 2
    assert all(model == "opus" and json_output for _, _, model, json_output in runner.calls)


# --- the jev claims arm (the real jev.check_claim path) ---


@pytest.mark.parametrize(
    "choice, confidence, verdict, shown, review",
    [
        ("supports", 0.8, "verified", 0.8, False),  # CHOICE_SURE itself is accepted
        # review compares the unrounded confidence: shown as 0.8, still sent to review
        ("contradicts", 0.7999, "contradicted", 0.8, True),
        ("says_nothing", 0.95, "unsupported", 0.95, False),
    ],
)
def test_check_claim_maps_the_choice_and_sends_low_confidence_to_review(
    tmp_path, choice, confidence, verdict, shown, review
):
    src = tmp_path / "a.py"
    src.write_text("x = 1\n")
    ask = fake_ask(lambda s, q: {"relation": {"choice": choice, "confidence": confidence, "probabilities": {}}})

    out = ej.jev.check_claim({"claim": "c", "file": str(src), "quote": "x = 1"}, ask)

    assert (out["verdict"], out["confidence"], out["review"]) == (verdict, shown, review)
    [(state, questions)] = ask.calls
    # key order matters: the state is part of the cache key
    assert list(state.items()) == [("claim", "c"), ("section", "x = 1")]
    assert questions == {"relation": ej.jev.RELATION_QUESTION}


def test_jev_arm_replays_every_stored_claims_case_from_the_cache(monkeypatch):
    # Guards the cache keys: a changed RELATION_QUESTION, state shape or Claude prompt would
    # miss here and need paid calls to reproduce results.json.
    def no_call(*args, **kwargs):
        raise AssertionError("cache miss: a live model call was attempted")

    monkeypatch.setattr(ej, "run_claude", no_call)
    cases = json.loads((ej.HERE / "claims_cases.json").read_text())
    labels = {x["id"]: x for x in json.loads((ej.HERE / "labels_independent.json").read_text())["claims"]}

    rows = ej.run_claims(cases, labels, no_call, ej.Cache(ej.HERE / "cache.json"))

    stored = json.loads((ej.HERE / "results.json").read_text())["claims"]
    assert rows == stored


# --- runs, with fakes (memgate goes through the real jev.cmd_memgate) ---


def test_run_claims_sends_claude_section_exactly_what_the_jev_arm_sends(tmp_path, monkeypatch):
    monkeypatch.setattr(ej, "HERE", tmp_path)
    lines = [f"line {i}" for i in range(1, 61)]
    lines[29] = "timeout = 30"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "conf.py").write_text("\n".join(lines) + "\n")
    whole = (tmp_path / "src" / "conf.py").read_text()

    def reply(system, text, n):
        if system == ej.CLAIMS_SECTION_SYSTEM:
            return "contradicts"
        return ["supports", "supports or contradicts"][n]  # claude_rep gives an unparseable reply

    runner = fake_runner(reply)
    monkeypatch.setattr(ej, "run_claude", runner)
    ask = fake_ask(lambda s, q: {"relation": {"choice": "contradicts", "confidence": 0.95, "probabilities": {}}})
    case = {"id": "c1", "kind": "value", "claim": "timeout is 60", "file": "src/conf.py", "quote": "timeout = 30",
            "gold_section": "contradicted", "gold_file": "contradicted", "note": ""}
    labels = {"c1": {"id": "c1", "label_section": "contradicted", "label_file": "contradicted",
                     "ambiguous": False, "note": ""}}

    [row] = ej.run_claims([case], labels, ask, ej.Cache(tmp_path / "cache.json"))

    [(jev_state, _)] = ask.calls
    k = ej.jev.CLAIM_CONTEXT_LINES
    assert jev_state["section"] == "\n".join(lines[29 - k : 30 + k])  # the quote's line 30, ±k lines
    assert jev_state["section"] != whole.rstrip("\n")
    [section_input] = [json.loads(t) for s, t, *_ in runner.calls if s == ej.CLAIMS_SECTION_SYSTEM]
    assert section_input == {"claim": "timeout is 60", "section": jev_state["section"]}
    file_inputs = [json.loads(t) for s, t, *_ in runner.calls if s == ej.CLAIMS_FILE_SYSTEM]
    assert file_inputs == [{"claim": "timeout is 60", "file": "src/conf.py", "content": whole}] * 2
    assert (row["jev"], row["jev_review"], row["clear"], len(row["jev_seconds"])) == ("contradicted", False, True, 1)
    assert (row["claude_section"], row["claude_file"], row["claude_rep"]) == ("contradicted", "verified", None)
    assert row["raw"]["claude_rep"] == "supports or contradicts"
    assert row["usage"]["claude_file"] == USAGE


EXISTING = """## Relevant past runs (3 of 9 in memory)

1. [SUCCESS] 2026-09-01 — "add retry to http client" (match 0.80)
   Learnings:
   - SDK retries 429 by default
2. [SUCCESS] 2026-09-02 — "migrate db schema" (match 0.40)
   Result: done
3. [FAILURE] 2026-09-03 — "flaky test" (match 0.30)
   Result: gave up
"""


def test_run_memgate_goes_through_cmd_memgate_and_shows_claude_the_same_record(tmp_path, monkeypatch):
    runner = fake_runner(lambda system, text, n: ["record", "Duplicate."][n])
    monkeypatch.setattr(ej, "run_claude", runner)

    def respond(state, questions):
        if "existing" not in state:
            return {"reuse": 0.9, "durable": 0.9, "actionable": 0.9, "noise": 0.1}
        return {"duplicate": 0.95 if "retries 429" in state["existing"] else 0.1, "conflict": 0.1}

    ask = fake_ask(respond)
    # a learning starting with "--" must stay a value, not be parsed as an option
    learnings = ["--tools '' keeps tools out", "SDK retries 429"]
    case = {"id": "m1", "gold": "duplicate", "source": "jev", "target": "1", "task": "retry http",
            "outcome": "success", "result": "done", "learnings": learnings, "existing": EXISTING, "note": ""}
    labels = {"m1": {"id": "m1", "label": "duplicate", "ambiguous": True, "note": ""}}

    [row] = ej.run_memgate([case], labels, ask, ej.Cache(tmp_path / "cache.json"))

    assert row["jev"] == "duplicate"
    # one request for the record plus one per existing entry, each timed
    assert len(ask.calls) == 4 and len(row["jev_seconds"]) == 4
    record = {"task": "retry http", "outcome": "success", "result": "done", "learnings": learnings}
    assert all(state["record"] == record for state, _ in ask.calls)
    claude_inputs = [json.loads(t) for _, t, *_ in runner.calls]
    assert claude_inputs == [{"record": record, "existing": ej.jev.parse_numbered(EXISTING)}] * 2
    assert len(claude_inputs[0]["existing"]) == 3
    assert (row["claude"], row["claude_rep"]) == ("record", "duplicate")
    assert row["clear"] is False  # the annotator agreed with gold but flagged the case ambiguous


def test_check_cases_lists_every_broken_case(tmp_path, monkeypatch):
    monkeypatch.setattr(ej, "HERE", tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    claim = {"id": "c1", "file": "a.py", "quote": "x = 1", "gold_section": "verified", "gold_file": "verified"}
    memory = {"id": "m1", "gold": "record", "task": "t", "outcome": "success", "result": "r",
              "learnings": ["l"], "existing": ""}
    ej.check_cases([claim], [memory])  # valid cases pass

    claims = [claim, {**claim, "id": "c2", "quote": "x = 2"}, {**claim, "id": "c3", "file": "gone.py"},
              {**claim, "id": "c4", "gold_file": "true"}]
    memgate = [memory, {**memory, "id": "m2", "outcome": "SUCCESS"}, {**memory, "id": "m3", "gold": "uncertain"}]
    with pytest.raises(ValueError) as error:
        ej.check_cases(claims, memgate)
    message = str(error.value)
    assert [i for i in ["c1", "c2", "c3", "c4", "m1", "m2", "m3"] if f"{i}:" in message] == ["c2", "c3", "c4", "m2", "m3"]
    with pytest.raises(ValueError, match="duplicate id c1"):
        ej.check_cases([claim, claim], [])


# --- report ---


def test_report_gives_the_numbers_the_decision_rule_needs():
    results = {
        "claims": [
            claims_row("c1", "verified", "verified", False, "verified"),
            claims_row("c2", "contradicted", "verified", False, "contradicted"),  # veto
            claims_row("c3", "contradicted", "contradicted", True, None),  # reviewed; claude unparsed
            claims_row("c4", "unsupported", "unsupported", False, "unsupported", clear=False),
        ],
        "memgate": [
            memgate_row("m1", "record", "skip", "record", [0.2, 0.4]),  # jev loses a learning
            memgate_row("m2", "conflict", "conflict", "duplicate", [0.2, 0.3, 0.5]),
            memgate_row("m3", "record", "record", "record", [0.2]),
            memgate_row("m4", "duplicate", "uncertain", "duplicate", [0.1, 0.6], clear=False),
        ],
    }
    text = ej.report(results)
    claims, memgate = text.split("\n## memgate\n")
    clear_claims, all_claims = claims.split("### claims: clear")[1].split("### claims: all")
    clear_memgate, all_memgate = memgate.split("### memgate: clear")[1].split("### memgate: all")

    assert "| jev | gold_section | 2/3 (67%) |" in clear_claims
    assert "- coverage: 2/3 (67%)" in clear_claims
    assert "- jev accuracy: 1/2 (50%)" in clear_claims
    assert "- claude_file accuracy on the same cases: 2/2 (100%)" in clear_claims
    assert "veto errors (gold_file contradicted -> jev verified): 1 ['c2']" in clear_claims
    assert "no action defined for these): 0 []" in clear_claims
    assert "- coverage: 2/4 (50%)" in all_claims
    assert "no action defined for these): 1 ['c4']" in all_claims

    assert "- coverage: 2/3 (67%)" in clear_memgate
    assert "- claude accuracy on the same cases: 2/2 (100%)" in clear_memgate
    assert "- jev precision per verdict: record 1/1 (100%), skip 0/1 (0%), duplicate -" in clear_memgate
    assert "- conflict recall: jev 1/1 (100%), claude 0/1 (0%)" in clear_memgate
    assert "jev 1 ['m1'], claude 0 []" in clear_memgate
    assert "| record | 0 | 0 | 1 | 1 |" in clear_memgate  # jev: gold record -> skip once, record once
    [jev_verdicts] = [line for line in all_memgate.splitlines() if line.startswith("- jev verdicts:")]
    assert "uncertain 1" in jev_verdicts

    assert "| claims | claude_file | 10 / 40 | 0 / 0 | 0 / 0 | 2 / 8 | 0.0100 / 0.0400 | 900 / 3600 |" in text
    # requests per case [2, 3, 1, 2]; per-request seconds median 0.25; per-case sums [0.6, 1.0, 0.2, 0.7]
    assert "| memgate | 2 | 0.25 | 0.65 / 2.50 |" in text
    assert "claims c3 claude_section: 'maybe'" in text


# --- evalkit.run_claude ---


def completed(stdout, returncode=0):
    return lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, stdout, "boom")


def test_run_claude_json_isolates_the_call_and_reads_usage(monkeypatch):
    seen = {}
    out = {"type": "result", "is_error": False, "result": " supports\n", "total_cost_usd": 0.02,
           "duration_ms": 1500, "usage": {"input_tokens": 12, "output_tokens": 3, "cache_read_input_tokens": 4000}}

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return completed(json.dumps(out))(command)

    monkeypatch.setattr(evalkit.subprocess, "run", fake_run)
    reply = evalkit.run_claude("SYS", "INPUT", "opus", json_output=True)

    # cache_creation_input_tokens is absent from usage, so it counts as 0
    assert reply == {"text": "supports", "input_tokens": 12, "output_tokens": 3, "cache_read_tokens": 4000,
                     "cache_creation_tokens": 0, "cost_usd": 0.02, "duration_ms": 1500}
    command = seen["command"]
    pairs = list(zip(command, command[1:]))
    for pair in [("--model", "opus"), ("--tools", ""), ("--setting-sources", ""), ("--output-format", "json")]:
        assert pair in pairs
    assert {"--strict-mcp-config", "--no-session-persistence"} <= set(command)
    assert command[-3:] == ["--system-prompt", "SYS", "INPUT"]  # the prompt stays the last argument
    assert seen["cwd"] == tempfile.gettempdir()


def test_run_claude_text_mode_returns_the_stripped_reply(monkeypatch):
    seen = []
    monkeypatch.setattr(evalkit.subprocess, "run", lambda command, **kw: seen.append(command) or completed("self\n")(command))
    assert evalkit.run_claude("SYS", "INPUT", "opus") == "self"
    assert "--output-format" not in seen[0]


@pytest.mark.parametrize(
    "stdout, returncode",
    [(json.dumps({"is_error": True, "result": "API Error: 529", "total_cost_usd": 0, "duration_ms": 0}), 0),
     ("", 1)],
)
def test_run_claude_raises_instead_of_returning_an_error_as_an_answer(monkeypatch, stdout, returncode):
    monkeypatch.setattr(evalkit.subprocess, "run", completed(stdout, returncode))
    with pytest.raises(RuntimeError, match="claude -p failed"):
        evalkit.run_claude("SYS", "INPUT", "opus", json_output=True)


def test_run_claude_sends_images_through_stream_json(monkeypatch):
    seen = {}
    events = [{"type": "system"}, {"type": "assistant"},
              {"type": "result", "is_error": False, "result": " {\"present\": true}\n", "total_cost_usd": 0.03,
               "duration_ms": 900, "usage": {"input_tokens": 1500, "output_tokens": 9}}]

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return completed("\n".join(map(json.dumps, events)))(command)

    monkeypatch.setattr(evalkit.subprocess, "run", fake_run)
    reply = evalkit.run_claude("SYS", "FIND", "opus", json_output=True, images=[b"\x89PNG one", b"\x89PNG two"])

    assert reply["text"] == '{"present": true}' and reply["cost_usd"] == 0.03 and reply["input_tokens"] == 1500
    command = seen["command"]
    assert command[-2:] == ["--system-prompt", "SYS"] and "FIND" not in command  # the text travels on stdin
    assert ("--input-format", "stream-json") in list(zip(command, command[1:]))
    content = json.loads(seen["input"])["message"]["content"]
    assert [c["type"] for c in content] == ["image", "image", "text"] and content[2]["text"] == "FIND"
    assert content[1]["source"]["data"] == "iVBORyB0d28="  # base64 of the second image
