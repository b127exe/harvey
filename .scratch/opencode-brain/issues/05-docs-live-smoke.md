# 05: Docs + live smoke

**What to build:** The fork documents how to run Harvey on OpenCode (including cheap-model guidance like MiMo v2.5 / DeepSeek via `provider/model`), and a one-time live smoke proves the real CLI end-to-end: parser fixtures locked against actual `opencode run --format json` output, `harvey status --check` ready, and one tiny brain call succeeds with the operator's model.

**Blocked by:** 03 (CLI, setup wizard, train surface).

**Status:** resolved

- [x] README gains a "Using OpenCode" section parallel to the Codex section (config keys, setup path, Windows-supported note, no-Harvey-cost-gauge note pointing at `opencode stats`)
- [x] CLAUDE.md Q&A mentions the OpenCode option; CHANGELOG entry added
- [x] One live `opencode run --format json` capture used to confirm/adjust the adapter's event parser and test fixtures
- [x] Live smoke: `harvey status --check` reports ready with operator's auth; one minimal `Brain.think()` returns text on a cheap model (e.g. MiMo v2.5 or DeepSeek)
- [x] Any parser/fixture adjustments from the live run land with tests still green

## Comments

- Live smoke results (2026-10-25, `opencode-go/mimo-v2.5`): preflight OK; `think("Respond with exactly: HARVEY_READY")` returned `HARVEY_READY`; usage row recorded with tokens + cost; `harvey status --check` prints "OpenCode (opencode-go/mimo-v2.5) ready".
- The live run exposed a Windows bug: a bare `opencode` is resolved through the npm `.cmd` shim, and cmd.exe re-parses it unquoted — it split the install path at the space in `Author Software` and failed. Fix: `_cli_command()` resolves the full path via `shutil.which` in `run`/`preflight` (regression test in test_opencode.py; suite green, 427 passed).
- The brain block was written into the tracked `harvey.yaml` rather than `harvey.local.yaml`, because the local file fully replaces the config (no merge) and a partial one breaks `load_config()`.
- README edits beyond the new section (intro, prerequisites, troubleshooting entry, structure comment) keep adjacent text consistent with the third provider.
