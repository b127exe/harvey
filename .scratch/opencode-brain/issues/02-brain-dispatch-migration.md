# 02: Brain dispatch + usage migration

**What to build:** When the brain provider is opencode, `Brain.think()` runs a full one-shot cycle — retry with backoff on transient failures, kill on timeout, pause on non-retryable auth/setup errors — and records token usage with `provider="opencode"` into a new per-provider usage counter. Heartbeat can complete a cycle against a stubbed OpenCode CLI.

**Blocked by:** 01 (OpenCode adapter + config acceptance).

**Status:** resolved

- [x] Schema migration adds an `opencode_calls` counter to the usage log (mirrors the codex migration); provider validation accepts `opencode`
- [x] Brain provider labels include OpenCode; client construction uses the plain (non-Codex) quota path for opencode
- [x] `think()` dispatches opencode to a one-shot loop shaped like the Claude path (backoff retry, timeout kill, non-retryable auth short-circuit) using the 01 adapter for command build + usage parse
- [x] Usage events recorded with `provider="opencode"`; state summary exposes the opencode call count
- [x] Brain-level tests (subprocess monkeypatch seam): opencode argv shape, canned JSON events → returned text, auth error → pause, transient → retry, timeout killed; claude and codex paths still green

## Comments

- Review fix: `usage_limit` is checked before `retryable` in `_think_opencode` — the adapter marks it retryable, but retrying an exhausted account must pause instead (brain-level test added).
- Full heartbeat-cycle proof against a stubbed OpenCode CLI was not added as a separate harness; the live end-to-end smoke in ticket 05 covers this. All brain-level acceptance tests pass.
