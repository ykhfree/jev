# Simulator fixture for evals/vision

`VisionFixture` is a SwiftUI app with five fixture screens (made-up data only).
The UI test `CaptureTests` opens each screen and the iOS Settings app.
For each one it writes a screenshot (`<screen>.png`) and the accessibility frames of all elements (`<screen>.json`).
The frames are the ground truth for the `sim` suite in `eval_vision.py`.

Needs Xcode with an iOS simulator runtime and `xcodegen` (Homebrew). The test boots the simulator without opening a window.

```bash
cd evals/vision/sim
xcodegen generate                                   # VisionFixture.xcodeproj (git-ignored)
OUT=$(mktemp -d)
TEST_RUNNER_OUT_DIR=$OUT xcodebuild test -project VisionFixture.xcodeproj -scheme VisionFixture \
  -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath "$OUT/dd"
cd .. && ~/.local/pipx/venvs/jev/bin/python eval_vision.py --import-sim "$OUT"
```

xcodebuild passes `TEST_RUNNER_OUT_DIR` to the test runner as `OUT_DIR`.
The runner writes there directly, because simulator processes can write host paths.
`sim_cases.py` picks each target out of the dump by element type, identifier and label.
