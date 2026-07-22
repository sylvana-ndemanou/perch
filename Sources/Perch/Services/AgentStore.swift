import Foundation
import Combine

/// The app's single source of truth. Polls every registered provider on a
/// timer, merges the results into a sorted list of agents, and forwards quick
/// actions back to the owning provider.
@MainActor
final class AgentStore: ObservableObject {
    static let shared = AgentStore()

    /// Every agent across all providers, sorted so the ones needing attention
    /// float to the top.
    @Published private(set) var agents: [Agent] = []

    /// How often to refresh, in seconds.
    var refreshInterval: TimeInterval = 3

    private var providers: [AgentProvider]
    private var timer: Timer?

    init(providers: [AgentProvider] = [ClaudeCodeProvider(), CursorProvider()]) {
        self.providers = providers
        start()
    }

    /// True when any agent is blocked waiting on the user — drives the menu bar
    /// icon's "attention" state.
    var hasAttention: Bool {
        agents.contains { $0.state.isActionable }
    }

    /// Register an additional provider (e.g. a user-added custom agent).
    func add(_ provider: AgentProvider) {
        providers.append(provider)
        Task { await refresh() }
    }

    func start() {
        Task { await refresh() }
        let timer = Timer(timeInterval: refreshInterval, repeats: true) { [weak self] _ in
            Task { await self?.refresh() }
        }
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    /// Pull a fresh snapshot from every provider and republish.
    func refresh() async {
        var collected: [Agent] = []
        for provider in providers {
            collected.append(contentsOf: await provider.poll())
        }
        agents = collected.sorted(by: Self.priority)
    }

    /// Run a quick action against the agent's owning provider, then refresh.
    @discardableResult
    func perform(_ action: AgentAction, on agent: Agent) async -> Bool {
        guard let provider = providers.first(where: { $0.kind == agent.kind }) else {
            return false
        }
        let ok = await provider.perform(action, on: agent)
        if ok { await refresh() }
        return ok
    }

    /// Sort: agents awaiting input first, then working, then everything else;
    /// ties broken by most-recently-updated.
    private static func priority(_ lhs: Agent, _ rhs: Agent) -> Bool {
        func rank(_ state: AgentState) -> Int {
            switch state {
            case .awaitingInput: return 0
            case .working: return 1
            case .idle: return 2
            case .done: return 3
            case .failed: return 4
            }
        }
        let l = rank(lhs.state), r = rank(rhs.state)
        if l != r { return l < r }
        return lhs.updatedAt > rhs.updatedAt
    }
}
