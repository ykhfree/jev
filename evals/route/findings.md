# Findings

## Run 1: summary context (2026-09-27 run: jev default model, claude -p opus)

- Primary limitation: `recent_context` is a hand-written one-line summary of session state. A real
  UserPromptSubmit hook gets the prompt plus a raw transcript path, not this summary. The with-context
  result shows Jev can read a good summary; routing from a raw transcript tail is untested. If Claude
  writes the summary, Claude has already made the judgment.
- Ceiling: the independent annotator agreed on 52/52 labels (7 flagged ambiguous) and Claude scored
  100% in both samples, so this set cannot show whether a Jev suggestion helps Claude. "0 broken" is
  not evidence of safety: every suggestion was correct, so the harm mode (a confident wrong suggestion)
  was never exercised.
- Prompt-only Jev (what a hook without context sees) is 100% where the prompt carries the decision and
  50% on context-dependent cases ("2번 해줘", rule 1's "already read the file"): it fails exactly where
  the policy depends on session state.
- Jev confidence is lowest on rule-1 cases (self; 0.39-0.87). A 0.5 gate would have withheld 1 of 45
  suggestions (r1h).
- Composing Nouls in code (jev_rules) scored 69%: `answer_only` fired 0.66-0.95 on design/decision
  requests ("정해줘", "판단해줘"), and `exact_edit_known` fired on fully specified multi-file edits
  (w7, w11). Not tuned on this data.
- Policy finding, not a Jev finding: rule 1 and rule 5 overlap when the session has already read the
  files of a fully specified multi-file edit (w7, w11); the text does not say which wins in spirit.

## Run 2: raw transcript context (2026-09-27, 21 context-dependent cases, Jev only)

`raw_contexts.json` replaces the one-line summary with a synthetic raw transcript tail (6.0k-6.5k chars:
earlier unrelated turns, an earlier decoy numbered list, Read/Bash/Grep tool output, Claude's prose),
written by three agents from each case's facts; no transcript contains the final message or a
handler name, and one added difficulty hint (w11 "기계적으로 반복하면 되는 작업") was removed.

- Jev Choice routed 21/21 (clear 18/18) from the raw tail, the same as from the summary; prompt-only
  stays at 11/21. The same short prompts ("2번 해줘", "3번 진행해줘") went to self, feature-developer,
  fast-worker, or deep-reasoner depending on the transcript, so it is reading the transcript, not
  keying on the prompt shape.
- Confidence dropped on most cases (e.g. r1d 0.83 -> 0.53, f11 0.69 -> 0.30). With the 0.5 gate,
  2/21 suggestions would be withheld (r1h 0.39, f11 0.30); rule-1 (self) cases sit at 0.39-0.75, so a
  0.7 gate would withhold most of them.
- Noul composition from raw text fell to 10/21: the single Choice is the only viable question shape.
- Rule 1 is detectable from the transcript (10/10: Jev reads the `[tool_use Read]` events), which
  revises run 1's claim that it needs state Jev cannot see; it is not confidently detectable.
- Design blocker for a hook: the tail it would send contains `tool_result` blocks (file contents,
  env dumps, logs). The global CLAUDE.md forbids sending secrets to Jev, and `jev.py` guards only by
  filename (`SECRET_NAME`), which a transcript bypasses. A content-redaction step must exist first.
- Limits: the transcripts are LLM-written from known facts, so the relevant facts are more salient,
  and all 21 landed at the floor of the requested 6k-12k range; a real tail sized to the token limit
  would be 4-5x longer with real tool dumps. Jev latency on a 6k state was not measured; a hook must still decide how much of the real
  transcript to pass (Jev: 32k tokens for state + longest question). Whether a suggestion helps or
  misleads Claude is still untested (Claude was at 100% in run 1, and the harm mode never occurred).

## Run 3: harm test and latency (2026-09-27)

- Confidently wrong suggestion on the 45 clear cases (`claude_wrong`; the wrong label is Jev's own
  best non-gold label, 29/45 of them "self" on agent tasks): Claude (opus) kept the correct answer
  45/45 — broken 0, same as its own repeat-sample noise (0 flips).
- Influence on the 7 ambiguous cases (nudged toward Jev's best label other than Claude's answer,
  which matched the annotator's stated alternative in most cases): 0/7 switched.
- So in a dedicated routing call with the policy in the system prompt, the suggestion neither helped
  nor hurt Opus: it was inert. Untested: a real main session, where routing is a side decision inside
  a long context, and weaker main-session models (Sonnet/Haiku), where the cookbook saw its gains.
- Latency: Jev Choice-only call with a 6k-char transcript state, 5 uncached calls: median 0.24 s,
  max 0.30 s (network included); answers matched the 7-question request.

## Run 4: Claude on the raw transcript context (2026-09-28)

`measure_claude_raw.py` runs the `claude` arm (claude -p opus, same system prompt) on the 21
`raw_contexts.json` tails, one call at a time; per-case rows in `claude_raw_results.json`.

- Claude routed 21/21 (clear 18/18), the same as Jev raw: the raw tail gives Jev no accuracy edge.
- Latency per isolated call: median 3.57 s (2.40-12.06 s; the 12 s case produced 407 output tokens),
  including claude -p process start. Jev on the same state: 0.24 s (run 3).
- Cost per isolated call: median $0.043 (about 5.3k cache-creation tokens, output median 9 tokens).
