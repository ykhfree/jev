import SwiftUI

// Fixture screens for evals/vision. The UI test picks one with `-screen <name>`.
// Every screen uses made-up data only.
@main
struct FixtureApp: App {
    var body: some Scene {
        WindowGroup {
            switch UserDefaults.standard.string(forKey: "screen") ?? "" {
            case "s_signin": SignInScreen()
            case "s_inbox": InboxScreen()
            case "s_settings": SettingsScreen()
            case "s_alert": AlertScreen()
            case "s_gallery": GalleryScreen()
            default: Text("unknown screen")
            }
        }
    }
}

struct SignInScreen: View {
    @State private var email = ""
    @State private var password = ""
    @State private var remember = true

    var body: some View {
        NavigationStack {
            Form {
                Section("Account") {
                    TextField("Email", text: $email).accessibilityIdentifier("email")
                    SecureField("Password", text: $password).accessibilityIdentifier("password")
                    Toggle("Remember me", isOn: $remember).accessibilityIdentifier("remember")
                }
                Section {
                    HStack(spacing: 12) {
                        Button("Cancel") {}.buttonStyle(.bordered).accessibilityIdentifier("cancel")
                        Button("Sign In") {}.buttonStyle(.borderedProminent).accessibilityIdentifier("signin")
                    }
                    Button("Forgot password?") {}.accessibilityIdentifier("forgot")
                }
            }
            .navigationTitle("Sign In")
        }
    }
}

struct InboxScreen: View {
    let messages = [
        ("Mina Park", "Lunch on Friday?"),
        ("Leo Kim", "Invoice #2041"),
        ("Sara Choi", "Design review notes"),
        ("Jun Lee", "Weekend hiking trip"),
        ("Ana Cho", "Re: build failures"),
    ]

    var body: some View {
        TabView {
            NavigationStack {
                List(messages, id: \.0) { sender, subject in
                    VStack(alignment: .leading) {
                        Text(sender).font(.headline)
                        Text(subject).foregroundStyle(.secondary)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("msg_" + sender.split(separator: " ")[0].lowercased())
                }
                .navigationTitle("Inbox")
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) { Button("Edit") {}.accessibilityIdentifier("edit") }
                    ToolbarItemGroup(placement: .topBarTrailing) {
                        Button { } label: { Image(systemName: "line.3.horizontal.decrease.circle") }
                            .accessibilityIdentifier("filter")
                        Button { } label: { Image(systemName: "square.and.pencil") }
                            .accessibilityIdentifier("compose")
                    }
                }
            }
            .tabItem { Label("Inbox", systemImage: "tray") }
            Text("Search").tabItem { Label("Search", systemImage: "magnifyingglass") }
            Text("Calendar").tabItem { Label("Calendar", systemImage: "calendar") }
            Text("Profile").tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
    }
}

struct SettingsScreen: View {
    @State private var wifi = true
    @State private var bluetooth = false
    @State private var fontSize = 3
    @State private var theme = "Dark"
    @State private var volume = 0.6

    var body: some View {
        NavigationStack {
            Form {
                Section("Connections") {
                    Toggle("Wi-Fi", isOn: $wifi).accessibilityIdentifier("wifi")
                    Toggle("Bluetooth", isOn: $bluetooth).accessibilityIdentifier("bluetooth")
                }
                Section("Display") {
                    Stepper("Font size: \(fontSize)", value: $fontSize, in: 1...7).accessibilityIdentifier("fontsize")
                    Picker("Theme", selection: $theme) {
                        Text("Light").tag("Light")
                        Text("Dark").tag("Dark")
                        Text("Auto").tag("Auto")
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("theme")
                }
                Section("Sound") {
                    Slider(value: $volume).accessibilityIdentifier("volume")
                }
            }
            .navigationTitle("Settings")
        }
    }
}

struct AlertScreen: View {
    @State private var showAlert = true

    var body: some View {
        NavigationStack {
            List(1...6, id: \.self) { i in Text("Photo \(i).jpg") }
                .navigationTitle("Photos")
        }
        .alert("Delete 3 photos?", isPresented: $showAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) {}
        } message: {
            Text("This cannot be undone.")
        }
    }
}

struct GalleryScreen: View {
    let tiles: [(String, String, Color)] = [
        ("heart", "heart.fill", .red), ("star", "star.fill", .yellow), ("leaf", "leaf.fill", .green),
        ("moon", "moon.fill", .purple), ("cloud", "cloud.fill", .blue), ("flame", "flame.fill", .orange),
        ("bolt", "bolt.fill", .gray), ("drop", "drop.fill", .cyan), ("paw", "pawprint.fill", .brown),
    ]

    var body: some View {
        NavigationStack {
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 12) {
                ForEach(tiles, id: \.0) { id, symbol, color in
                    RoundedRectangle(cornerRadius: 12)
                        .fill(color.opacity(0.18))
                        .aspectRatio(1, contentMode: .fit)
                        .overlay(Image(systemName: symbol).font(.system(size: 44)).foregroundStyle(color))
                        .accessibilityElement()
                        .accessibilityAddTraits(.isImage)
                        .accessibilityIdentifier("tile_" + id)
                }
            }
            .padding()
            Spacer()
                .navigationTitle("Stickers")
        }
    }
}
