import SwiftUI

/// The popover shown when you click the Perch menu bar icon. Lists every
/// monitored agent, grouped so the ones needing attention are at the top.
struct MenuContentView: View {
    @EnvironmentObject private var store: AgentStore

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header

            Divider()

            if store.agents.isEmpty {
                emptyState
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(store.agents) { agent in
                            AgentRowView(agent: agent)
                        }
                    }
                    .padding(12)
                }
                .frame(maxHeight: 420)
            }

            Divider()

            footer
        }
        .frame(width: 340)
    }

    private var header: some View {
        HStack {
            Image(systemName: "bird.fill")
            Text("Perch")
                .font(.headline)
            Spacer()
            if store.hasAttention {
                Label("Needs you", systemImage: "exclamationmark.circle.fill")
                    .labelStyle(.iconOnly)
                    .foregroundStyle(.orange)
            }
        }
        .padding(12)
    }

    private var emptyState: some View {
        VStack(spacing: 6) {
            Image(systemName: "bird")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No agents running")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(24)
    }

    private var footer: some View {
        HStack {
            Button {
                Task { await store.refresh() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            Spacer()
            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
        }
        .buttonStyle(.plain)
        .font(.callout)
        .padding(12)
    }
}
