# 01: OpenCode adapter + config acceptance

**What to build:** Harvey's config accepts `brain.provider: opencode` with a free-form `provider/model` `brain.model`, and a new thin OpenCode adapter can run a one-shot `opencode run --format json` call, report its version/auth health via preflight, and classify failures (setup / auth / usage_limit / transient) — verified entirely with fakes, no heartbeat wiring yet.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Config provider list includes `opencode`; yaml loader accepts it; model validation for opencode requires a `provider/model` slash form; `reasoning_effort` accepted but unused on this path
- [ ] New adapter module exposes a run(prompt, timeout) result carrying final assistant text, model id, duration, and token usage parsed from JSON events (unknown event types ignored; missing final text = typed error)
- [ ] Prompts longer than 8k chars go via stdin, shorter via argv
- [ ] Preflight: CLI version command succeeds and an auth/credential check passes or raises a typed setup/auth error
- [ ] Typed errors carry kind ∈ {setup, auth, usage_limit, transient} and a retryable flag
- [ ] Adapter tests: fake CLI or monkeypatched subprocess cover happy path, JSON parsing, stdin switch, auth failure, timeout kill; no claude/codex behavior changes
