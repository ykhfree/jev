# Findings

## Pre-registration (written 2026-09-27, before any model call)

Question: is there a reason to keep `jev claims` and `jev memgate` in the "Jev decides" tier of the
global CLAUDE.md, or does Claude doing the judgment directly do as well? Route (`../route/`) was
dropped because Claude matched Jev; the same test applies here.

Arms:
- claims: `jev` (the real `check_claim` path), `claude_section` (the same ±15-line section Jev sees),
  `claude_file` (the whole file: the realistic alternative, Claude re-opening it), `claude_rep`
  (second sample of `claude_file`: the noise floor).
- memgate: `jev` (the real `cmd_memgate` path), `claude` (same record + same frozen `existing` list,
  same precedence conflict > duplicate > skip > record), `claude_rep` (noise floor).
- Claude arms have no abstain option. Jev is scored on the verdicts it acts on alone (claims
  `review: false`; memgate `record` / `skip` / `duplicate`) plus coverage; Claude on all cases.

Decision rule, per command, on clear cases (the blind annotator agrees with gold and does not flag
the case ambiguous):
- Keep in "Jev decides" only if Jev's accuracy on its autonomous verdicts >= the Claude arm's
  accuracy on those same cases (claims: `claude_file`; memgate: `claude`), with coverage >= 60%.
- claims: any `contradicted -> verified` error in Jev's autonomous tier (a false claim reported as
  true) moves claims to "Jev advises", whatever the totals.
- memgate: a Jev `skip` / `duplicate` on a gold `record` case loses a learning; if Jev does this more
  often than `claude`, memgate moves to "Jev advises".
- If Jev ties Claude, accuracy gives no reason to use Jev; the remaining argument is cost (Claude
  tokens and dollars per case, Jev latency), reported for the user to decide.

Limits known before running:
- ~40 cases per command: 0 errors bounds the error rate at about 7% (95%), not at zero.
- An isolated `claude -p` is not the main session judging its own claim or record, so the
  self-grading hypothesis (Jev as an independent reviewer) is not tested.

## Run 1 (2026-09-27, jev default model, claude -p opus)

Numbers in `report.md`; clear cases: claims 39/40, memgate 27/40.

Pre-registered rule applied:
- claims: the verdict on the coverage floor depends on the tier definition. The pre-registration
  says "claims `review: false`", which includes `unsupported` verdicts: 27/39 (69%, passes), Jev
  27/27 vs `claude_file` 27/27. The harness narrows the tier to verified/contradicted: 19/39 (49%,
  fails), 19/19 vs 19/19. The pre-registered text supports the broader reading, so claims is a tie
  with 0 veto errors: no accuracy reason to use Jev; the rule leaves it to cost and the user.
- claims, same ±15-line window: `claude_section` 39/39, Jev 34/39. All 5 Jev errors go one way:
  `verified` when the window does not show the fact (c23, c24, c26, c28, c40).
- memgate fails both: coverage 15/27 (56% < 60%), and Jev's autonomous verdicts are 14/15 against
  `claude` 15/15 on the same cases (m36: gold skip, Jev duplicate). Learnings lost on clear cases:
  0 vs 0; on all cases Jev lost 1 (m28, ambiguous), Claude 0. Both misses are one case wide:
  coverage needed 17/27, and m36's wrong label has the same action as gold (don't record), so
  action-level accuracy is 15/15.

Beyond the rule:
- The veto counted 0, but one autonomous claims verdict was right by luck: c24 (outside_window) got
  `verified` at confidence 0.93 while the section does not show the value the claim depends on (0.7
  is defined outside the window). Scored against gold_file it counts as correct. The other three
  outside_window guesses (c23, c26, c28; two of them wrong against the file) stayed under 0.8 and went
  to review. The ±15-line window invites guessing a constant's value.
- 8 claims got `unsupported` with review false (c32-c39, all correct): the global CLAUDE.md gives no
  action for this verdict.
- Claude never abstains and was right on every clear claims case and 26/27 clear memgate cases; Jev
  sent 9/27 clear memgate cases to `uncertain`, so Claude would have had to judge them anyway.
- Noise floor: claude_rep changed 0 claims verdicts and 1 clear memgate verdict (m11, toward gold).
- Cost: an isolated Claude call cost $0.01 (claims section) to $0.06 (whole file) per case and $0.02
  per memgate case, mostly cache creation for the system prompt and file. In the main session the
  memgate record and `existing` list are already in context, so the marginal cost there is a few
  output tokens; for claims, re-opening the file costs its tokens (median 7.6k here). Jev took a
  median 0.22 s (claims, 1 request) and 1.22 s summed (memgate, 6 requests) per case, and each
  request sends the text to an external API.
- Limits: memgate has only 5 clear `record` cases, so learnings lost rests on a small sample; the
  self-grading hypothesis is still untested.

## Decision (2026-09-27, the user)

- claims: the global CLAUDE.md no longer uses `jev claims`. The model-free quote check (returns `lines`
  and `section`, Claude judges the claim) is the `quote-check` skill (~/.claude/skills/quote-check).
  `jev claims` stays in the CLI unchanged, as the TypeSafe citation_check cookbook example.
- memgate: moved from "Jev decides" to "Jev advises" in the global CLAUDE.md, and the rule to always run
  it before recording was dropped.
