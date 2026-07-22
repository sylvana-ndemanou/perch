import XCTest
@testable import Perch

/// A provider we can drive from tests.
private struct MockProvider: AgentProvider {
    let id = "mock"
    let kind: AgentKind = .custom
    var agents: [Agent]
    func poll() async -> [Agent] { agents }
    func perform(_ action: AgentAction, on agent: Agent) async -> Bool { true }
}

@MainActor
final class AgentStoreTests: XCTestCase {
    func testRefreshSortsAgentsNeedingAttentionFirst() async {
        let provider = MockProvider(agents: [
            Agent(id: "a", kind: .custom, name: "idle-one", state: .idle),
            Agent(id: "b", kind: .custom, name: "waiting-one", state: .awaitingInput),
            Agent(id: "c", kind: .custom, name: "working-one", state: .working),
        ])
        let store = AgentStore(providers: [provider])
        store.stop() // don't let the timer race with the test

        await store.refresh()

        XCTAssertEqual(store.agents.map(\.state).first, .awaitingInput)
        XCTAssertEqual(store.agents.map(\.name), ["waiting-one", "working-one", "idle-one"])
    }

    func testHasAttentionReflectsAwaitingInput() async {
        let quiet = MockProvider(agents: [
            Agent(id: "a", kind: .custom, name: "x", state: .working),
        ])
        let store = AgentStore(providers: [quiet])
        store.stop()
        await store.refresh()
        XCTAssertFalse(store.hasAttention)

        store.add(MockProvider(agents: [
            Agent(id: "b", kind: .custom, name: "y", state: .awaitingInput),
        ]))
        await store.refresh()
        XCTAssertTrue(store.hasAttention)
    }
}
