"""Offline tests for the routing eval harness: no Jev or Claude calls."""

import eval_route as ev

ALL_NO = {k: 0.1 for k in ev.RULE_QUESTIONS}


def nouls(**yes):
    return {**ALL_NO, **yes}


def test_compose_rules_follows_rule_order():
    # rule 1 beats a costly decision that is also flagged
    assert ev.compose_rules(nouls(exact_edit_known=0.9, costly_decision_open=0.9), "fast-worker") == "self"
    assert ev.compose_rules(nouls(answer_only=0.8), "fast-worker") == "self"
    # rules 2/3 beat behavior change
    assert ev.compose_rules(nouls(approach_undecided=0.7, changes_behavior=0.9), "self") == "deep-reasoner"
    # rule 4 beats rule 5
    assert ev.compose_rules(nouls(changes_behavior=0.6, fully_specified=0.9), "self") == "feature-developer"
    assert ev.compose_rules(nouls(fully_specified=0.5), "self") == "fast-worker"


def test_compose_rules_falls_back_when_nothing_fires():
    assert ev.compose_rules(ALL_NO, "feature-developer") == "feature-developer"


def test_suggestion_block_gates_on_confidence():
    sure = ev.suggestion_block({"choice": "fast-worker", "confidence": 0.5})
    assert "fast-worker" in sure and "Ignore this" in sure
    unsure = ev.suggestion_block({"choice": "fast-worker", "confidence": 0.49})
    assert "fast-worker" not in unsure and "No handler stands out" in unsure


def test_plausible_wrong_picks_jevs_best_non_gold_label():
    probs = {"self": 0.7, "fast-worker": 0.2, "feature-developer": 0.1, "deep-reasoner": 0.0}
    assert ev.plausible_wrong(probs, "self") == "fast-worker"
    assert ev.plausible_wrong(probs, "fast-worker") == "self"
    # missing or tied probabilities fall back to LABELS order, never to the gold label
    assert ev.plausible_wrong({}, "self") == "deep-reasoner"


def test_parse_label():
    assert ev.parse_label("deep-reasoner") == "deep-reasoner"
    assert ev.parse_label("Self.") == "self"
    assert ev.parse_label("**fast-worker**\n") == "fast-worker"
    # two different labels, or none, is unparseable rather than a silent guess
    assert ev.parse_label("self or fast-worker") is None
    assert ev.parse_label("itself") is None
    assert ev.parse_label("I cannot decide") is None


def test_flips_counts_fixed_and_broken_against_gold():
    rows = [
        {"id": "a", "gold": "self", "x": "self", "y": "fast-worker"},  # broken
        {"id": "b", "gold": "self", "x": "fast-worker", "y": "self"},  # fixed
        {"id": "c", "gold": "self", "x": "fast-worker", "y": "deep-reasoner"},  # still wrong
        {"id": "d", "gold": "self", "x": "self", "y": "self"},  # still right
    ]
    assert ev.flips(rows, "x", "y") == (["b"], ["a"])


def test_run_builds_rows_from_cached_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "HERE", tmp_path)
    seen_claude = []

    def fake_claude(cache, arm, text):
        seen_claude.append((arm, text))
        return "fast-worker" if arm == "claude_jev" else "self"

    monkeypatch.setattr(ev, "ask_claude", fake_claude)

    def fake_ask(state, questions):
        with_context = bool(state["recent_context"])
        answers = {k: 0.1 for k in ev.RULE_QUESTIONS}
        answers["exact_edit_known"] = 0.9 if with_context else 0.1
        answers["route"] = {
            "choice": "self" if with_context else "fast-worker",
            "confidence": 0.8,
            "probabilities": {},
        }
        return answers

    case = {"id": "r1", "gold": "self", "rule": "1", "needs_context": True,
            "prompt": "2번 해줘", "context": "2) loader.py:48 timeout 30->60"}
    other = {**case, "id": "w1", "gold": "fast-worker"}
    raw = {"r1": "[assistant] 2) loader.py:48 timeout 30->60 ... (long transcript)"}
    row, row_no_raw = ev.run([case, other], {"r1": ("self", False)}, fake_ask, raw)

    assert row["clear"] is True
    assert (row["jev"], row["jev_prompt"], row["jev_rules"]) == ("self", "fast-worker", "self")
    assert (row["claude"], row["claude_rep"], row["claude_jev"]) == ("self", "self", "fast-worker")
    # harm arm runs only on clear cases, with a wrong label presented as a confident suggestion
    assert (row["wrong_suggestion"], row["claude_wrong"]) == ("deep-reasoner", "self")
    assert (row_no_raw["wrong_suggestion"], row_no_raw["claude_wrong"]) == (None, None)
    wrong_texts = [text for arm, text in seen_claude if arm == "claude_wrong"]
    assert len(wrong_texts) == 1 and "Relevant handler for the current request: deep-reasoner" in wrong_texts[0]
    # claude_jev's suggestion is built from the with-context Jev answer; the baselines get none
    suggested = [text for arm, text in seen_claude if arm == "claude_jev"]
    assert "Relevant handler for the current request: self" in suggested[0]
    assert all("agent_relevance" not in text for arm, text in seen_claude if arm in ("claude", "claude_rep"))
    assert (row["jev_raw"], row["jev_raw_rules"]) == ("self", "self")
    # cases without a raw transcript get no raw arm rather than a silent copy
    assert (row_no_raw["jev_raw"], row_no_raw["jev_raw_rules"]) == (None, None)
    assert (tmp_path / "cache.json").exists()


def test_cache_persists_every_concurrent_insert(tmp_path):
    cache = ev.Cache(tmp_path / "cache.json")
    ev.jev.pmap(lambda i: cache.get(["k", i], lambda: i * 2), range(40))
    reloaded = ev.Cache(tmp_path / "cache.json")
    assert sorted(reloaded.data.values()) == [i * 2 for i in range(40)]
    # a cached key is served without recomputing
    assert reloaded.get(["k", 3], lambda: "recomputed") == 6
