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
    ClaudeCodeProvider.swift  # real — backed by the hooks below
    CursorProvider.swift      # still sample data, see roadmap
  Views/
    MenuContentView.swift   # the popover
    AgentRowView.swift      # one agent card + its quick actions
Scripts/claude-code-hooks/   # hook scripts Claude Code runs (see setup below)
Tests/PerchTests/           # unit tests for the store
```

`ClaudeCodeProvider` is wired up to real sessions via Claude Code hooks (see
below). `CursorProvider` still returns sample data — Cursor integration is
tracked separately in the roadmap.

## Requirements

- macOS 13 (Ventura) or later — Perch uses SwiftUI's `MenuBarExtra`.
- Xcode 15+ / Swift 5.9+.
- `jq` for the Claude Code hook scripts: `brew install jq`.

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

## Quick launch (skip `swift run` every time)

```sh
make install     # builds a release binary and installs it as `perch`
perch            # launch it from anywhere, any time
```

`make install` (or `./Scripts/install.sh` directly) builds once in release
mode and copies the binary to `/usr/local/bin/perch`. Re-run it after pulling
changes to update the installed version.

## Setting up real Claude Code monitoring

Perch never talks to Claude Code directly — there's no API for that. Instead
it installs a few [hooks](https://code.claude.com/docs/en/hooks) that write
small state files to `~/Library/Application Support/Perch/`, which
`ClaudeCodeProvider` reads and writes to.

1. Make sure the scripts are executable (they already are in this repo, but
   just in case): `chmod +x Scripts/claude-code-hooks/*.sh`
2. Open (or create) `~/.claude/settings.json` and merge in the contents of
   [`Scripts/claude-code-hooks/settings-snippet.json`](Scripts/claude-code-hooks/settings-snippet.json).
   Update the paths inside it to wherever you actually cloned this repo — they
   default to `$HOME/perch/Scripts/claude-code-hooks/...`.
3. Restart any running Claude Code sessions (hooks are picked up at session
   start).
4. Run Perch (`swift run Perch`). Working sessions should show up, and any
   `Bash`, `Edit`, `Write`, or `NotebookEdit` call will pause — visible as
   "awaiting input" in Perch — until you approve or reject it there.

**What's real vs. not yet:**

- ✅ Session discovery, live status (idle/working/awaiting input), and
  approve/reject are real — driven by the `PreToolUse`, `SessionStart`,
  `Stop`, and `SessionEnd` hooks.
- ❌ **Interrupt** and **send message** aren't wired up. Claude Code's hook
  system doesn't currently expose a way to inject a message or cancel an
  in-flight turn from an external process, so these actions are present in
  the UI but no-ops for now rather than something faked to look functional.
- The `PreToolUse` matcher only gates `Bash|Edit|Write|NotebookEdit` by
  default — broaden it in the settings snippet if you want Perch to gate
  other tools too, at the cost of an extra ~0.5-1s round trip per call while
  Perch is idle (it's still polling locally, not over a network).

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## License

[MIT](LICENSE)
