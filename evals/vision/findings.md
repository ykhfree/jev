# Vision eval: findings

Run on 2026-10-16 with `jev-1.14.0` (TypeSafe images and Box are Danger Zone, "Dreamer-ready").
Numbers are in `report.md`. This file records the design and what the numbers mean.

## Question

Can Jev take UI judgments off Claude during screen development?

1. **which**: which screenshots show a target.
2. **locate**: where a target is in one screenshot, as a click point.

## Design

- `pages.py` holds 8 synthetic screens: 6 desktop (1280x800, DPR 2) and 2 phone (390x844, DPR 3).
  They contain no real user data. Each target has a `data-t` id.
- Playwright (system Chrome) renders each screen. The DOM box of each target is the ground truth,
  so labels cost nothing.
- 38 locate cases (30 present, 8 absent) and 8 which queries x 8 screens.
- Images go through `jev.image_size` (280..1568 px per side). Jev sees the same PNG that `jev` sends.
- Claude baseline: `claude -p` (opus) with the same screenshot, sized under 1.15 MP so its pixel
  answers map back. It answers presence and a pixel box.
- The pass bar for the marker check was set before its run: flag at least 80% of wrong boxes,
  and at most 2 right ones.

## Results

| judgment | Jev | Claude |
|---|---|---|
| which, per (query, screen) pair | 64/64 | 64/64 |
| presence (locate) | 38/38 | 38/38 |
| click point inside target, Box only | 25/30 | 30/30 |
| click point inside target, Box + zoom crop | 22/30 | - |
| marker check: wrong boxes flagged / right boxes flagged | 5/5, 1/25 | - |

- **which**: the margins are wide. Gold screens scored 0.97 or more; other screens scored 0.04 or less.
  This holds for a target on 5 of 8 screens (the header cart icon) and for a near miss
  (checkbox vs toggle).
- **Box misses have a shape.** The SDK says each edge is the expected value of its predicted position.
  Between two similar neighbours (Cancel next to Create account, gear next to bell, Billing next to
  Privacy), the box spans both and its center lands between them or on the wrong one.
- **Box confidence does not separate misses.** Misses had confidence 0.23 to 0.79; hits went down to 0.26.
- **Zoom made it worse (negative result).** The crop removes the context that the description
  depends on: "the row of order #103" or "the toggle for SMS". 5 hits became misses and 2 misses
  became hits. Do not retry
  zoom without keeping that context.
- **The marker check works on this set.** A red ring at the click point on the full screenshot,
  then a Noul: "is the marker placed on X?" The full screenshot keeps the context.
  All 24 boxes that passed the check were correct.
- **Cost and latency.** A Jev request took about 0.22 s with about 4,000 input tokens per image.
  An isolated Claude call took about 4.7 s and $0.02 (locate) or $0.10 (which, 8 images).
  In a live session, Claude's marginal cost for an image already in context is lower.
  The Jev advantage is context and latency, not dollars.

## Decisions

- Ship `jev which`. It matches Claude and keeps screenshots out of Claude's context.
- Ship `jev locate` as Box + marker check. Act on the click point only when `verdict` is `ok`.
  If `verdict` is `unverified`, Claude reads the screenshot itself.
- Thresholds (`LOCATE` in `jev.py`) are the 0.5 cuts this eval used. They were not tuned.

## Limits

- 30 present targets and 5 Box misses are a small sample. One right box was flagged
  (`orders-del102`, 0.35), so expect some extra fallbacks to Claude.
- All screens are synthetic and simple. Real apps have denser layouts and more look-alike
  neighbours. Run this eval on real dev screens before widening the rule.
- macOS app and simulator captures were not measured. On this Mac, `xcrun simctl` did not
  respond (no simulator runtime is installed), so the simulator capture path is not verified.
- Images are a Danger Zone feature. Re-run this eval and `tests/test_live.py` on each new Jev release.
