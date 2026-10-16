import XCTest

// Captures each fixture screen and dumps the accessibility frames of its elements.
// Output goes to $OUT_DIR on the host (pass TEST_RUNNER_OUT_DIR to xcodebuild).
final class CaptureTests: XCTestCase {
    static let fixtureScreens = ["s_signin", "s_inbox", "s_settings", "s_alert", "s_gallery"]

    func testCaptureScreens() throws {
        let out = try XCTUnwrap(ProcessInfo.processInfo.environment["OUT_DIR"])
        for screen in Self.fixtureScreens {
            let app = XCUIApplication()
            app.launchArguments = ["-screen", screen]
            app.launch()
            try capture(app, as: screen, to: out)
            app.terminate()
        }
        let settings = XCUIApplication(bundleIdentifier: "com.apple.Preferences")
        settings.launch()
        try capture(settings, as: "s_sysprefs", to: out)
        settings.terminate()
    }

    private func capture(_ app: XCUIApplication, as name: String, to out: String) throws {
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20))
        Thread.sleep(forTimeInterval: 2.5)  // let launch and alert animations settle
        // screenshot and frames come from the same moment
        let png = XCUIScreen.main.screenshot().pngRepresentation
        let root = try app.snapshot()
        var elements: [[String: Any]] = []
        walk(root, into: &elements)
        let window = root.frame
        let dump: [String: Any] = [
            "window": [window.minX, window.minY, window.width, window.height],
            "elements": elements,
        ]
        try png.write(to: URL(fileURLWithPath: "\(out)/\(name).png"))
        let json = try JSONSerialization.data(withJSONObject: dump, options: [.prettyPrinted, .sortedKeys])
        try json.write(to: URL(fileURLWithPath: "\(out)/\(name).json"))
    }

    private func walk(_ node: XCUIElementSnapshot, into elements: inout [[String: Any]]) {
        let f = node.frame
        if f.width > 0, f.height > 0 {
            elements.append([
                "type": typeName(node.elementType),
                "id": node.identifier,
                "label": node.label,
                "frame": [f.minX, f.minY, f.width, f.height],
            ])
        }
        for child in node.children { walk(child, into: &elements) }
    }

    private func typeName(_ t: XCUIElement.ElementType) -> String {
        switch t {
        case .button: return "button"
        case .cell: return "cell"
        case .staticText: return "text"
        case .switch: return "switch"
        case .toggle: return "toggle"
        case .slider: return "slider"
        case .stepper: return "stepper"
        case .image: return "image"
        case .textField: return "textField"
        case .secureTextField: return "secureTextField"
        case .segmentedControl: return "segmented"
        case .alert: return "alert"
        case .tabBar: return "tabBar"
        case .navigationBar: return "navBar"
        case .searchField: return "searchField"
        case .other: return "other"
        default: return "type\(t.rawValue)"
        }
    }
}
