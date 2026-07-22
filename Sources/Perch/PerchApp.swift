import SwiftUI

/// Perch — a macOS menu bar app that keeps an eye on your local AI agents.
///
/// The whole app lives in the menu bar (no dock icon, no window). It uses
/// `MenuBarExtra` so the popover content is plain SwiftUI, and an
/// `AgentStore` that polls the registered providers on a timer.
@main
struct PerchApp: App {
    @StateObject private var store = AgentStore.shared

    var body: some Scene {
        MenuBarExtra {
            MenuContentView()
                .environmentObject(store)
        } label: {
            // A little bird on a perch — swap for a custom asset later.
            Image(systemName: store.hasAttention ? "bird.fill" : "bird")
        }
        .menuBarExtraStyle(.window)
    }
}
