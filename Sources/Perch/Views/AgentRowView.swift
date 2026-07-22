import SwiftUI

/// A single agent's card: what it is, what it's doing, progress, and the quick
/// actions available for its current state.
struct AgentRowView: View {
    let agent: Agent
    @EnvironmentObject private var store: AgentStore
    @State private var message = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: agent.kind.symbolName)
                    .foregroundStyle(.secondary)
                Text(agent.name)
                    .font(.system(.body, design: .rounded))
                    .fontWeight(.medium)
                Spacer()
                StatusBadge(state: agent.state)
            }

            if let task = agent.currentTask {
                Text(task)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            if let progress = agent.progress, agent.state == .working {
                ProgressView(value: progress)
                    .progressViewStyle(.linear)
            }

            if let request = agent.pendingRequest {
                Text(request)
                    .font(.callout)
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.orange.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }

            actions
        }
        .padding(10)
        .background(Color.primary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    @ViewBuilder
    private var actions: some View {
        if agent.state == .awaitingInput {
            HStack {
                actionButton(.approve, tint: .green)
                actionButton(.reject, tint: .red)
                actionButton(.interrupt, tint: .secondary)
            }
        } else if agent.state == .working {
            HStack {
                actionButton(.interrupt, tint: .secondary)
            }
        }

        HStack(spacing: 6) {
            TextField("Message…", text: $message)
                .textFieldStyle(.roundedBorder)
                .onSubmit(send)
            Button(action: send) {
                Image(systemName: AgentAction.sendMessage("").symbolName)
            }
            .buttonStyle(.borderless)
            .disabled(message.trimmingCharacters(in: .whitespaces).isEmpty)
        }
    }

    private func actionButton(_ action: AgentAction, tint: Color) -> some View {
        Button {
            Task { await store.perform(action, on: agent) }
        } label: {
            Label(action.label, systemImage: action.symbolName)
        }
        .buttonStyle(.bordered)
        .tint(tint)
        .controlSize(.small)
    }

    private func send() {
        let text = message.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }
        Task { await store.perform(.sendMessage(text), on: agent) }
        message = ""
    }
}

/// Small colored pill showing an agent's state.
struct StatusBadge: View {
    let state: AgentState

    var body: some View {
        Text(label)
            .font(.caption2)
            .fontWeight(.semibold)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.18))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }

    private var label: String {
        switch state {
        case .idle: return "Idle"
        case .working: return "Working"
        case .awaitingInput: return "Needs you"
        case .done: return "Done"
        case .failed: return "Failed"
        }
    }

    private var color: Color {
        switch state {
        case .idle: return .secondary
        case .working: return .blue
        case .awaitingInput: return .orange
        case .done: return .green
        case .failed: return .red
        }
    }
}
