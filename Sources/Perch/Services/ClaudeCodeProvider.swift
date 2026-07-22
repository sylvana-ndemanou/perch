import Foundation
#if canImport(Darwin)
import Darwin
#endif

/// Surfaces locally running Claude Code sessions.
///
/// Real sessions never talk to this app directly — instead, Perch installs a
/// few hooks into `~/.claude/settings.json` (see `Scripts/claude-code-hooks/`
/// and the README) that write small JSON state files under
/// `~/Library/Application Support/Perch/`. This provider reads that shared
/// state, forwards approve/reject decisions back by writing a decision file
/// the `PreToolUse` hook is polling for, and interrupts a session by sending
/// it `SIGINT` directly — the same signal a terminal `Ctrl+C` sends, which
/// Claude Code already treats as "stop the current turn".
///
/// - `sessions/<id>.json` — current status for a session (idle/working/
///   awaitingInput/done), including the real `claude` process's pid, written
///   by the SessionStart, PreToolUse, and Stop hooks.
/// - `pending/<id>.json` — the tool call currently awaiting a decision,
///   present only while a `PreToolUse` hook is blocked and polling.
/// - `decisions/<id>.json` — written by this provider's `perform(_:on:)`,
///   consumed and deleted by the polling hook.
///
/// `.sendMessage` isn't wired up — the only way to inject a message into a
/// running Claude Code session is a separate, undocumented WebSocket
/// protocol (`--sdk-url`) that requires Perch to *launch* the session itself
/// rather than attach to one already running in a terminal. That's a
/// deliberately out-of-scope tradeoff for this pass — see the README.
struct ClaudeCodeProvider: AgentProvider {
    let id = "claude-code"
    let kind: AgentKind = .claudeCode

    private let baseDir: URL = {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return support.appendingPathComponent("Perch", isDirectory: true)
    }()

    private var sessionsDir: URL { baseDir.appendingPathComponent("sessions", isDirectory: true) }
    private var pendingDir: URL { baseDir.appendingPathComponent("pending", isDirectory: true) }
    private var decisionsDir: URL { baseDir.appendingPathComponent("decisions", isDirectory: true) }

    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    func poll() async -> [Agent] {
        let fm = FileManager.default
        try? fm.createDirectory(at: sessionsDir, withIntermediateDirectories: true)

        guard let sessionFiles = try? fm.contentsOfDirectory(at: sessionsDir, includingPropertiesForKeys: nil) else {
            return []
        }

        return sessionFiles.compactMap { url -> Agent? in
            guard url.pathExtension == "json" else { return nil }
            let sessionId = url.deletingPathExtension().lastPathComponent

            guard let data = try? Data(contentsOf: url),
                  let session = try? Self.decoder.decode(SessionRecord.self, from: data)
            else { return nil }

            let pendingURL = pendingDir.appendingPathComponent("\(sessionId).json")
            let pending = (try? Data(contentsOf: pendingURL))
                .flatMap { try? Self.decoder.decode(PendingRequest.self, from: $0) }

            let state: AgentState = pending != nil ? .awaitingInput : session.status
            let currentTask = pending.map { "\($0.toolName): \($0.summary)" } ?? session.lastTool

            return Agent(
                id: "claude-code/\(sessionId)",
                kind: .claudeCode,
                name: session.projectName,
                state: state,
                currentTask: currentTask,
                pendingRequest: pending?.summary,
                updatedAt: session.updatedAt
            )
        }
        .sorted { $0.updatedAt > $1.updatedAt }
    }

    @discardableResult
    func perform(_ action: AgentAction, on agent: Agent) async -> Bool {
        // agent.id is "claude-code/<session-id>" — see poll() above.
        guard let sessionId = agent.id.split(separator: "/", maxSplits: 1).last else { return false }

        switch action {
        case .approve:
            return writeDecision(["decision": "allow"], sessionId: String(sessionId))
        case .reject:
            return writeDecision(["decision": "deny", "reason": "Denied from Perch"], sessionId: String(sessionId))
        case .interrupt:
            return sendInterrupt(sessionId: String(sessionId))
        case .sendMessage:
            // No channel for this on an already-running terminal session — see the type's doc comment above.
            return false
        }
    }

    /// Sends SIGINT to the session's `claude` process — the same signal a
    /// terminal `Ctrl+C` sends, which Claude Code already treats as
    /// "interrupt the current turn" rather than terminating the process.
    private func sendInterrupt(sessionId: String) -> Bool {
        let url = sessionsDir.appendingPathComponent("\(sessionId).json")
        guard let data = try? Data(contentsOf: url),
              let session = try? Self.decoder.decode(SessionRecord.self, from: data),
              let pid = session.pid
        else { return false }

        // Refuse to signal pid 0/1 or anything that isn't actually running —
        // a stale record shouldn't let us send SIGINT to an unrelated process.
        guard pid > 1, kill(pid, 0) == 0 else { return false }
        return kill(pid, SIGINT) == 0
    }

    private func writeDecision(_ payload: [String: String], sessionId: String) -> Bool {
        let fm = FileManager.default
        try? fm.createDirectory(at: decisionsDir, withIntermediateDirectories: true)
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return false }
        let url = decisionsDir.appendingPathComponent("\(sessionId).json")
        return (try? data.write(to: url, options: .atomic)) != nil
    }
}

private struct SessionRecord: Codable {
    let projectName: String
    let status: AgentState
    let lastTool: String?
    let updatedAt: Date
    let pid: Int32?
}

private struct PendingRequest: Codable {
    let toolName: String
    let summary: String
}
