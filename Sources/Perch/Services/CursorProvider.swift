import Foundation

/// Surfaces agent activity from a locally running Cursor instance.
///
/// The real implementation will connect to Cursor (e.g. via a companion
/// extension or its local state) to report background-agent progress. For now
/// it returns a representative sample.
struct CursorProvider: AgentProvider {
    let id = "cursor"
    let kind: AgentKind = .cursor

    func poll() async -> [Agent] {
        // TODO: connect to Cursor and map its agents to Agent values.
        [
            Agent(
                id: "cursor/dashboard",
                kind: .cursor,
                name: "dashboard",
                state: .working,
                currentTask: "Refactoring the settings view",
                progress: 0.25
            ),
        ]
    }

    @discardableResult
    func perform(_ action: AgentAction, on agent: Agent) async -> Bool {
        // TODO: forward the action to Cursor.
        NSLog("CursorProvider: \(action.label) -> \(agent.id)")
        return true
    }
}
