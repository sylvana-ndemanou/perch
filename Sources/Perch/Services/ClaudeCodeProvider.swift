import Foundation

/// Surfaces locally running Claude Code sessions.
///
/// The real implementation will watch Claude Code's session/state on disk
/// (under `~/.claude`) and/or hook into its permission prompts to detect when a
/// session is waiting on the user. For now this returns a representative sample
/// so the UI can be built and demoed end to end.
struct ClaudeCodeProvider: AgentProvider {
    let id = "claude-code"
    let kind: AgentKind = .claudeCode

    func poll() async -> [Agent] {
        // TODO: read ~/.claude sessions and map them to Agent values.
        [
            Agent(
                id: "claude-code/perch",
                kind: .claudeCode,
                name: "perch",
                state: .working,
                currentTask: "Scaffolding the menu bar app",
                progress: 0.6
            ),
            Agent(
                id: "claude-code/api",
                kind: .claudeCode,
                name: "billing-api",
                state: .awaitingInput,
                currentTask: "Run database migration",
                pendingRequest: "Allow `psql` to run migration 0042?"
            ),
        ]
    }

    @discardableResult
    func perform(_ action: AgentAction, on agent: Agent) async -> Bool {
        // TODO: forward the action to the Claude Code session.
        NSLog("ClaudeCodeProvider: \(action.label) -> \(agent.id)")
        return true
    }
}
