# Vision eval: findings

Run on 2026-10-16 with `jev-1.14.0` (TypeSafe images and Box are Danger Zone, "Dreamer-ready").
Numbers are in `report.md`. This file records the design and what the numbers mean.

## Question

Can Jev take UI judgments off Claude during screen development?

1. **which**: which screenshots show a target.
2. **locate**: where a target is in one screenshot, as a click point.

## Design

Two suites. Each has exact ground truth, so labels cost nothing.

- **web**: `pages.py` holds 8 synthetic screens: 6 desktop (1280x800, DPR 2) and 2 phone
  (390x844, DPR 3). Playwright (system Chrome) renders them. Each target has a `data-t` id,
  and its DOM box is the truth. 38 locate cases (30 present) and 8 which queries x 8 screens.
- **sim**: `sim/` holds a SwiftUI fixture app with 5 screens. The 6th screen is the iOS Settings app
  (Korean system language, no signed-in account). An XCUITest captures each screen on the
  iPhone 17 simulator (iOS 27.0, 1206x2622 px). It dumps the accessibility frames at the same moment,
  and these frames are the truth. `sim_cases.py` holds 31 locate cases (25 present) and
  10 which queries x 6 screens.
- No screen in either suite holds real user data.
- Images go through `jev.image_size` (280..1568 px per side). Jev sees the same PNG that `jev` sends.
- Claude baseline: `claude -p` (opus) with the same screenshot, sized under 1.15 MP so its pixel
  answers map back. It answers presence and a pixel box.
- The pass bar for the marker check was set before its first run: flag at least 80% of wrong boxes,
  and at most 2 right ones.

## Results

| judgment | web: Jev | web: Claude | sim: Jev | sim: Claude |
|---|---|---|---|---|
| which, per (query, screen) pair | 64/64 | 64/64 | 59/60 | 60/60 |
| which, gold screen ranked first (or none) | 8/8 | - | 10/10 | - |
| presence (locate) | 38/38 | 38/38 | 29/31 | 31/31 |
| click point inside target, Box only | 25/30 | 30/30 | 24/25 | 25/25 |
| click point inside target, Box + zoom crop | 22/30 | - | 22/25 | - |
| marker check: wrong boxes flagged | 5/5 | - | 1/1 | - |
| marker check: right boxes flagged | 1/25 | - | 1/24 | - |

- **which**: the gold screen ranked first on all 18 queries. On 16 of them the margins were wide,
  including near misses: checkbox vs toggle (web), and the Search tab vs a search field (sim).
  The other 2 are the low-presence targets below.
- **Box misses have a shape.** The SDK says each edge is the expected value of its predicted position.
  Between two similar neighbours, the box spans both. Its center lands between them or on the
  wrong one. Web: Cancel next to Create account, gear next to bell. Sim: the 'Auto' segment
  (the box covered the whole picker; the center fell on 'Dark').
- **The flagged right box in sim was a near miss.** For the stepper's + button, the box covered
  both - and +. Its center was 2.6 pt inside the + frame, on the divider. Flagging it was the safe call.
- **Box confidence does not separate misses.** Web misses had confidence 0.23 to 0.79;
  hits went down to 0.26.
- **Zoom made it worse in both suites (negative result).** The crop removes the context that the
  description depends on: "the row of order #103" or "the toggle for SMS". Do not retry zoom
  without keeping that context.
- **The marker check works.** A red ring at the click point on the full screenshot, then a Noul:
  "is the marker placed on X?" The full screenshot keeps the context. All 47 boxes that passed
  the check (24 web, 23 sim) were correct.
- **Presence can miss controls without a visible label (sim only).** The filter icon (0.28) and the
  volume slider (0.42; no "volume" text on screen) were present but scored low. Claude found both.
  `locate` then returns `absent`, which Claude must check. Two `which` queries tested this directly.
  "A filter icon button" still ranked the inbox screen first, but at 0.11, so `no_match` (<= 0.3)
  would have said no screen shows it. "A volume slider" ranked first at 0.73. Ranking holds;
  `no_match` does not, so `no_match` from `which` is advisory in the global CLAUDE.md.
- **Cost and latency.** A Jev request took about 0.2 to 0.3 s with 3,000 to 4,000 input tokens per image.
  An isolated Claude call took about 4.5 s and $0.02 (locate), or $0.08 to $0.10 (which, 6 to 8 images).
  In a live session, Claude's marginal cost for an image already in context is lower.
  The Jev advantage is context and latency, not dollars.

## Decisions

- Ship `jev which`. Its ranking matched Claude, and it keeps screenshots out of Claude's context.
  Its ranking is reliable; its `no_match` is advisory.
- Ship `jev locate` as Box + marker check. Act on the click point only when `verdict` is `ok`.
  If `verdict` is `unverified` or `absent`, Claude reads the screenshot itself.
- Thresholds (`LOCATE` in `jev.py`) are the 0.5 cuts this eval used. They were not tuned.

## Capture paths checked on this Mac (2026-10-16, Xcode 27.1)

- iOS 27.0 and watchOS 27.0 simulator runtimes are installed. Xcode 27.1 has no `Simulator.app`;
  `xcodebuild test` and `xcrun simctl` boot the simulator without a window.
- `xcrun simctl io <device> screenshot` gives the same 1206x2622 PNG as the XCUITest capture.
  `jev locate` on such a capture of the Settings app returned `ok`. The frames came from a different
  boot, so this was checked by eye on the marker image: the click was on the '일반' row.
- A fresh boot showed a different Settings layout than the XCUITest run (no "검색 및 Siri 최적화 중"
  banner). Take the screenshot and any ground truth at the same moment.
- One earlier `xcrun simctl` call hung for over 2 minutes; run it in the background.

## Limits

- 55 present targets, 6 Box misses and 2 presence misses are a small sample.
- All fixture screens are simple. Real apps have denser layouts and more look-alike neighbours.
  Run this eval on real dev screens before widening the rules.
- macOS app captures (`screencapture -l <windowid>`) were not measured.
- Images are a Danger Zone feature. Re-run this eval and `tests/test_live.py` on each new Jev release.
