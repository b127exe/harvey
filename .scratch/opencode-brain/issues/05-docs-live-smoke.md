# 05: Docs + live smoke

**What to build:** The fork documents how to run Harvey on OpenCode (including cheap-model guidance like MiMo v2.5 / DeepSeek via `provider/model`), and a one-time live smoke proves the real CLI end-to-end: parser fixtures locked against actual `opencode run --format json` output, `harvey status --check` ready, and one tiny brain call succeeds with the operator's model.

**Blocked by:** 03 (CLI, setup wizard, train surface).

**Status:** ready-for-agent

- [ ] README gains a "Using OpenCode" section parallel to the Codex section (config keys, setup path, Windows-supported note, no-Harvey-cost-gauge note pointing at `opencode stats`)
- [ ] CLAUDE.md Q&A mentions the OpenCode option; CHANGELOG entry added
- [ ] One live `opencode run --format json` capture used to confirm/adjust the adapter's event parser and test fixtures
- [ ] Live smoke: `harvey status --check` reports ready with operator's auth; one minimal `Brain.think()` returns text on a cheap model (e.g. MiMo v2.5 or DeepSeek)
- [ ] Any parser/fixture adjustments from the live run land with tests still green
