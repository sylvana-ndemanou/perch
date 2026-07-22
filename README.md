# Perch 🐦

A macOS menu bar app that keeps an eye on your local AI agents.

Perch lives in your menu bar and aggregates every AI coding agent running on
your Mac — **Claude Code**, **Cursor**, and any agent you add — so you can see
what they're each doing at a glance and act on them without switching tools.

## What it does

- **See every agent in one place.** A single popover lists all your local
  agents with their current task and live progress.
- **Know when you're needed.** The menu bar icon flags when any agent is
  blocked waiting on you (a permission prompt, a question), so you don't have to
  babysit terminals.
- **Take quick actions.** Approve or reject a request, interrupt a task, or send
  a message to an agent — straight from the menu bar.
- **Bring your own agents.** Claude Code and Cursor ship as built-in providers;
  add more by implementing a small `AgentProvider`.

## Project layout

```
Sources/Perch/
  PerchApp.swift            # @main app — the MenuBarExtra scene
  Models/
    Agent.swift             # Agent, AgentKind, AgentState
    AgentAction.swift       # approve / reject / interrupt / send message
  Services/
    AgentProvider.swift     # protocol every integration implements
    AgentStore.swift        # polls providers, merges + sorts agents
    ClaudeCodeProvider.swift
    CursorProvider.swift
  Views/
    MenuContentView.swift   # the popover
    AgentRowView.swift      # one agent card + its quick actions
Tests/PerchTests/           # unit tests for the store
```

The provider implementations currently return representative sample data so the
UI can be built and demoed end to end; wiring them up to the real tools is the
next milestone (see the roadmap).

## Requirements

- macOS 13 (Ventura) or later — Perch uses SwiftUI's `MenuBarExtra`.
- Xcode 15+ / Swift 5.9+.

## Build & run

```sh
swift build          # compile
swift run Perch      # run the menu bar app
swift test           # run the unit tests
```

You can also open `Package.swift` in Xcode and run the `Perch` scheme.

> **Note:** to ship this as a proper menu-bar-only app (no Dock icon) you'll
> want an app bundle with `LSUIElement = YES` in its `Info.plist`. That
> packaging step is tracked in the roadmap.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## License

[MIT](LICENSE)
