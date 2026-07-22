import Foundation
import SwiftUI

/// The kind of tool an agent is running under. `.custom` covers any agent the
/// user wires up beyond the built-in Claude Code and Cursor providers.
enum AgentKind: String, Codable, Hashable {
    case claudeCode = "Claude Code"
    case cursor = "Cursor"
    case custom = "Custom"

    /// SF Symbol used to represent the agent kind in the menu.
    var symbolName: String {
        switch self {
        case .claudeCode: return "sparkles"
        case .cursor: return "cursorarrow.rays"
        case .custom: return "cpu"
        }
    }

    /// Accent color used throughout the row (icon, left edge, badges) so
    /// Claude Code and Cursor agents read as visually distinct at a glance.
    var accentColor: Color {
        switch self {
        case .claudeCode: return Color(red: 0.82, green: 0.47, blue: 0.31) // Claude's warm terracotta
        case .cursor: return Color(red: 0.35, green: 0.55, blue: 1.0)       // Cursor's blue
        case .custom: return .secondary
        }
    }

    /// Whether this provider currently has a real channel for `.sendMessage`.
    /// Claude Code doesn't — injecting a message into an already-running
    /// terminal session isn't possible via hooks (see `ClaudeCodeProvider`'s
    /// doc comment) — so the message field is hidden rather than shown and
    /// silently doing nothing.
    var supportsSendMessage: Bool {
        switch self {
        case .claudeCode: return false
        case .cursor, .custom: return true
        }
    }
}

/// Lifecycle state of an agent's current task.
enum AgentState: String, Codable, Hashable {
    /// Idle — connected but not working on anything.
    case idle
    /// Actively working on a task.
    case working
    /// Blocked, waiting for the user to approve/reject or answer a question.
    case awaitingInput
    /// Finished its task successfully.
    case done
    /// Failed or errored out.
    case failed

    var isActionable: Bool { self == .awaitingInput }
}

/// A single monitored agent and the task it is currently running.
struct Agent: Identifiable, Hashable {
    let id: String
    var kind: AgentKind
    /// Human-friendly name, usually the project or session the agent is in.
    var name: String
    var state: AgentState
    /// A short description of what the agent is doing right now.
    var currentTask: String?
    /// Progress of the current task, 0...1, when the agent reports it.
    var progress: Double?
    /// When set, the prompt the agent is waiting on the user to resolve.
    var pendingRequest: String?
    var updatedAt: Date

    init(
        id: String,
        kind: AgentKind,
        name: String,
        state: AgentState = .idle,
        currentTask: String? = nil,
        progress: Double? = nil,
        pendingRequest: String? = nil,
        updatedAt: Date = Date()
    ) {
        self.id = id
        self.kind = kind
        self.name = name
        self.state = state
        self.currentTask = currentTask
        self.progress = progress
        self.pendingRequest = pendingRequest
        self.updatedAt = updatedAt
    }
}
