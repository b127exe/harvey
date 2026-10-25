# 02: Brain dispatch + usage migration

**What to build:** When the brain provider is opencode, `Brain.think()` runs a full one-shot cycle — retry with backoff on transient failures, kill on timeout, pause on non-retryable auth/setup errors — and records token usage with `provider="opencode"` into a new per-provider usage counter. Heartbeat can complete a cycle against a stubbed OpenCode CLI.

**Blocked by:** 01 (OpenCode adapter + config acceptance).

**Status:** ready-for-agent

- [ ] Schema migration adds an `opencode_calls` counter to the usage log (mirrors the codex migration); provider validation accepts `opencode`
- [ ] Brain provider labels include OpenCode; client construction uses the plain (non-Codex) quota path for opencode
- [ ] `think()` dispatches opencode to a one-shot loop shaped like the Claude path (backoff retry, timeout kill, non-retryable auth short-circuit) using the 01 adapter for command build + usage parse
- [ ] Usage events recorded with `provider="opencode"`; state summary exposes the opencode call count
- [ ] Brain-level tests (subprocess monkeypatch seam): opencode argv shape, canned JSON events → returned text, auth error → pause, transient → retry, timeout killed; claude and codex paths still green
