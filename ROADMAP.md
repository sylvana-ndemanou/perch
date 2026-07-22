# Perch roadmap

## Now — scaffolding

- [x] Menu bar app shell (`MenuBarExtra`), popover UI, agent cards
- [x] `AgentProvider` protocol + `AgentStore` polling loop
- [x] Built-in providers stubbed with sample data (Claude Code, Cursor)
- [x] Quick actions modeled: approve / reject / interrupt / send message
- [x] Unit tests for store sorting + attention state

## Next — real integrations

- [ ] Claude Code provider: read `~/.claude` sessions and detect permission
      prompts / task progress
- [ ] Cursor provider: connect to Cursor to report background-agent progress
- [ ] Wire quick actions through to each tool (approve/reject/interrupt/message)
- [ ] Notifications when an agent starts waiting on the user

## Later — polish & distribution

- [ ] Menu-bar-only app bundle (`LSUIElement`) + code signing / notarization
- [ ] Custom agent providers configurable from a Settings pane
- [ ] Custom Perch menu bar icon (replace the SF Symbol placeholder)
- [ ] Launch at login
- [ ] Per-agent history / recent activity view
