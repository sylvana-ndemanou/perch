import Foundation

/// A source of agents. Each supported tool (Claude Code, Cursor, …) ships one
/// provider; users can add more by conforming to this protocol.
///
/// Providers are intentionally simple: `poll()` returns the current snapshot of
/// every agent the provider knows about, and `perform(_:on:)` applies a quick
/// action. Discovery/transport (reading local session files, talking to a
/// socket, etc.) is each provider's own business.
protocol AgentProvider {
    /// Stable identifier for the provider, e.g. "claude-code".
    var id: String { get }

    /// The kind of agents this provider surfaces.
    var kind: AgentKind { get }

    /// Return the current snapshot of all agents this provider can see.
    func poll() async -> [Agent]

    /// Apply a quick action to one of this provider's agents.
    /// - Returns: `true` when the action was accepted.
    @discardableResult
    func perform(_ action: AgentAction, on agent: Agent) async -> Bool
}
