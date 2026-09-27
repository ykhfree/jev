| arm | all | clear | clear+needs_context | clear+no_context |
|---|---|---|---|---|
| jev | 52/52 (100%) | 45/45 (100%) | 18/18 (100%) | 27/27 (100%) |
| jev_prompt | 42/52 (81%) | 36/45 (80%) | 9/18 (50%) | 27/27 (100%) |
| jev_rules | 36/52 (69%) | 34/45 (76%) | 13/18 (72%) | 21/27 (78%) |
| claude | 52/52 (100%) | 45/45 (100%) | 18/18 (100%) | 27/27 (100%) |
| claude_rep | 52/52 (100%) | 45/45 (100%) | 18/18 (100%) | 27/27 (100%) |
| claude_jev | 52/52 (100%) | 45/45 (100%) | 18/18 (100%) | 27/27 (100%) |

Jev confidence gate (clear cases): threshold -> coverage, accuracy of covered
  >= 0.0: 45/45 covered, 100% correct
  >= 0.3: 45/45 covered, 100% correct
  >= 0.5: 44/45 covered, 100% correct
  >= 0.7: 39/45 covered, 100% correct
  >= 0.9: 33/45 covered, 100% correct

claude -> claude_rep (clear): fixed 0 [], broken 0 []

claude -> claude_jev (clear): fixed 0 [], broken 0 []

claude -> claude_wrong (clear): fixed 0 [], broken 0 []

jev errors (gold -> picked): 

claude errors (gold -> picked): 

Raw transcript context (21 context-dependent cases)

| arm | all | clear |
|---|---|---|
| jev | 21/21 (100%) | 18/18 (100%) |
| jev_raw | 21/21 (100%) | 18/18 (100%) |
| jev_raw_rules | 10/21 (48%) | 9/18 (50%) |
| jev_prompt | 11/21 (52%) | 9/18 (50%) |

jev_raw per case (gold -> picked, confidence summary -> raw):
  ok  a4: self -> self  (0.99 -> 0.99)
  ok  r1a: self -> self  (0.52 -> 0.60)
  ok  r1b: self -> self  (0.75 -> 0.74)
  ok  r1c: self -> self  (0.67 -> 0.60)
  ok  r1d: self -> self  (0.83 -> 0.53)
  ok  r1e: self -> self  (0.62 -> 0.65)
  ok  r1f: self -> self  (0.83 -> 0.63)
  ok  r1g: self -> self  (0.67 -> 0.62)
  ok  r1h: self -> self  (0.39 -> 0.39)
  ok  r1i: self -> self  (0.87 -> 0.75)
  ok  d2e: deep-reasoner -> deep-reasoner  (0.99 -> 0.96)
  ok  d2g: deep-reasoner -> deep-reasoner  (0.92 -> 0.90)
  ok  d2h: deep-reasoner -> deep-reasoner  (0.96 -> 0.83)
  ok  d3b: deep-reasoner -> deep-reasoner  (0.99 -> 0.93)
  ok  d3d: deep-reasoner -> deep-reasoner  (0.99 -> 0.86)
  ok  d3g: deep-reasoner -> deep-reasoner  (1.00 -> 0.90)
  ok  f3: feature-developer -> feature-developer  (0.92 -> 0.93)
  ok  f7: feature-developer -> feature-developer  (0.67 -> 0.66)
  ok  f11: feature-developer -> feature-developer  (0.69 -> 0.30)
  ok  w7: fast-worker -> fast-worker  (0.93 -> 0.88)
  ok  w11: fast-worker -> fast-worker  (0.95 -> 0.93)
