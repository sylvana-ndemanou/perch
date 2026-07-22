import Foundation

/// A quick action the user can take on an agent straight from the menu bar,
/// without opening the underlying tool.
enum AgentAction: Hashable {
    /// Approve the agent's pending request (e.g. a permission prompt).
    case approve
    /// Reject the agent's pending request.
    case reject
    /// Interrupt / stop the agent's current task.
    case interrupt
    /// Send a free-form text message to the agent.
    case sendMessage(String)

    var label: String {
        switch self {
        case .approve: return "Approve"
        case .reject: return "Reject"
        case .interrupt: return "Interrupt"
        case .sendMessage: return "Send"
        }
    }

    var symbolName: String {
        switch self {
        case .approve: return "checkmark.circle"
        case .reject: return "xmark.circle"
        case .interrupt: return "stop.circle"
        case .sendMessage: return "paperplane"
        }
    }
}
