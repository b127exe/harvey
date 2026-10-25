# Spec: OpenCode brain provider

Status: ready-for-agent
Branch: `feat/opencode-brain`

## Problem Statement

Harvey only runs on a Claude or Codex subscription. The fork owner has neither — they only have OpenCode (v1.19.4, installed and working on Windows). Without an OpenCode provider, Harvey cannot make a single brain call on this machine: `brain.provider` rejects anything but `claude`/`codex`, the Codex adapter refuses Windows outright, and the Claude path requires a logged-in Claude CLI the owner doesn't have. The fork is unusable for its intended purpose until OpenCode is a first-class brain provider.

## Solution

Add OpenCode as a third, opt-in brain provider. When `harvey.yaml` sets `brain.provider: opencode` with a free-form `brain.model` in `provider/model` form, every Harvey brain call (prospecting scoring, email writing, reply handling) runs as a one-shot `opencode run --format json -m <model>` subprocess — the same shape as the existing Claude path. Harvey works end-to-end on Windows for the first time (Codex remains Windows-refused; OpenCode does not). Claude and Codex behavior is unchanged; upstream merge stays simple because OpenCode is additive.

## User Stories

1. As a fork owner with only an OpenCode subscription, I want Harvey to use OpenCode as its brain, so that the agent runs without Claude or Codex.
2. As a Windows user, I want the OpenCode provider to work on Windows, so that I'm not blocked by the Codex platform refusal.
3. As a Harvey operator, I want to set `brain.provider: opencode` and a free-form `brain.model` (e.g. a cheap capable model such as MiMo v2.5 or a DeepSeek model available through my OpenCode providers) in `harvey.yaml`, so that I control which model OpenCode uses.
4. As a first-time setup user, I want `harvey setup` to offer opencode in the provider menu, check that `opencode` is on PATH, and ask for my model, so that I can configure Harvey without editing YAML by hand.
5. As an operator running `harvey status --check`, I want an opencode preflight (CLI present + auth OK), so that I learn about a broken login before the heartbeat starts failing.
6. As an operator, I want `harvey status` to show an "OpenCode calls today" counter, so that I can see agent activity at a glance.
7. As an operator, I want `harvey usage` to show OpenCode call counts (with subscription gauges marked n/a), so that I understand OpenCode spend is tracked outside Harvey (via `opencode stats` / my provider dashboard).
8. As an operator, I want token usage from each OpenCode call recorded into usage events with `provider="opencode"`, so that per-agent token attribution includes OpenCode calls.
9. As a long-prompt user, I want prompts over 8k characters passed via stdin rather than argv, so that OS argv limits don't break large agent prompts.
10. As an operator, I want a timed-out or hung `opencode run` process killed, so that the heartbeat never wedges on a stuck subprocess.
11. As an operator, I want non-retryable auth errors (not logged in / invalid credentials) to pause the brain with a clear reason rather than retry forever, so that I see one actionable error instead of a retry storm.
12. As an operator, I want transient OpenCode failures retried with backoff (same as Claude), so that brief CLI hiccups don't drop a cycle.
13. As a dashboard user, I want OpenCode call counts in pipeline stats and the usage API, so that the web UI reflects the active provider.
14. As a dashboard user, I want the quota card to show "unavailable" for OpenCode, so that I'm not shown fake subscription gauges.
15. As a `harvey train` user, I want `--provider opencode` accepted and written into `harvey.yaml`, so that retraining preserves my provider choice.
16. As a maintainer of this fork, I want OpenCode wired additively (no behavior change for claude/codex), so that the branch stays mergeable with upstream.
17. As a maintainer, I want OpenCode call counts in a new `opencode_calls` column (schema migration), so that the existing per-provider usage_log pattern stays intact.
18. As a developer, I want brain-level tests that capture the exact `opencode run` argv and feed canned JSON events, so that dispatch, retry, and usage parsing are verified without a real CLI.
19. As a developer, I want an adapter-level fake OpenCode CLI covering parse/auth/timeout scenarios, so that edge cases are tested cheaply.
20. As a documentation reader, I want a README "Using OpenCode" section parallel to the Codex one, so that setup is discoverable.
21. As a Harvey Q&A user, I want CLAUDE.md to mention the OpenCode option, so that in-project guidance matches the fork's purpose.
22. As an operator whose OpenCode model doesn't support a requested reasoning effort, I want `reasoning_effort` ignored for opencode, so that config doesn't fail spuriously.

## Implementation Decisions

- **Provider list**: brain providers become `claude`, `codex`, `opencode` in config validation, state validation, and all label/column maps.
- **Adapter depth**: minimal one-shot CLI adapter — deliberately not the Codex-depth adapter (no isolation attestations, no pinned-version gate, no rate-limit ledger). OpenCode's auth is whatever `opencode providers` already holds; Harvey does not manage it.
- **Subprocess contract**: `opencode run --format json -m <brain.model>` with the prompt on argv, switched to stdin when longer than 8,000 characters (mirrors the Claude argv-limit trick). Child inherits the operator environment (OpenCode auth lives outside Harvey's config). Timeout enforced by kill, same as Claude's run loop.
- **Output parsing**: stdout is a stream of JSON events (OpenCode `--format json` "raw JSON events"); the adapter extracts the final assistant text and token counts. Exact event shapes are confirmed against a live one-shot during implementation; the parser treats unknown event types as ignorable and fails with a typed error if no final text arrives.
- **Error taxonomy**: adapter raises a typed error with `kind` ∈ {`setup`, `auth`, `usage_limit`, `transient`} and a `retryable` flag. Auth/setup kinds pause the brain via the existing persistent-failure ledger (reusing the Codex pause machinery's provider-tagged status rows). Transient errors backoff-retry exactly like Claude's run loop. `usage_limit` starts a usage pause if observed; it is best-effort until a real OpenCode response proves the mapping.
- **Preflight**: cheap — `opencode --version` succeeds and an auth check (provider/credential listing) confirms the CLI can reach a model. Surfaced through the existing `brain.preflight()` / `harvey status --check` flow.
- **Dispatch**: `Brain.think()` gains an `opencode` branch that reuses the Claude one-shot loop shape (retry, timeout kill, non-retryable auth short-circuit) with an OpenCode command builder and usage parser. Claude-specific payload handling (modelUsage rows, session-id flag) stays Claude-only. No provider registry refactor — third branches/dict entries at each site, matching existing codebase style.
- **Model config**: free-form string in `provider/model` form; validated only as "contains a slash". `reasoning_effort` accepted in schema but ignored on the opencode path.
- **Database**: schema migration adds `opencode_calls` (integer, default 0) to `usage_log`, mirroring the codex migration. Usage events record `provider="opencode"`.
- **Quota gauges**: OpenCode has no Claude-/Codex-style subscription usage API; the usage command and dashboard quota card report calls-only and mark gauges unavailable. Operators use `opencode stats` for spend.
- **Platform**: OpenCode supported on Windows, macOS, and Linux (no `require_supported_platform` refusal, unlike Codex).
- **Branch**: all work on `feat/opencode-brain`; `main` untouched.
- **Default provider**: remains `claude` upstream; OpenCode is opt-in via config so the branch merges cleanly.

## Testing Decisions

- Tests assert external behavior only: the argv Harvey would execute, the user-visible text returned, pause/retry decisions, recorded usage rows, and CLI-config surfaces — never internal helper structure.
- **Brain-level seam (primary)**: extend the existing provider-plumbing suite that monkeypatches `asyncio.create_subprocess_exec` to capture commands and return canned process output. New cases: opencode argv shape (model flag, json format, no tools flags), stdin switch for long prompts, canned JSON-event → text/usage, auth error → pause, transient error → retry, timeout kill.
- **Adapter-level seam (secondary)**: a fake `opencode` CLI script (mirroring the existing fake Codex CLI) driven through the same subprocess-exec swap for parse/auth/timeout edge cases.
- **Config/surface tests**: provider accepted in yaml loader, setup wizard menu includes opencode, `harvey train --provider opencode` choices, status/usage label branches, dashboard stats columns — all in the existing provider test suite.
- Prior art: `tests/test_brain_provider.py` (Claude `_capture_exec`, `_StubCodex`), `tests/test_codex.py` + `tests/fake_codex.py`, `tests/test_brain_no_tools.py` (Claude argv assertions).
- No CI job installing a pinned OpenCode CLI initially; a live-CLI surface test can be added later behind an env gate like the Codex one.

## Out of Scope

- Codex-style isolation attestations, fingerprint-gated rechecks, pinned-version gates, or a rate-limit/quota ledger for OpenCode.
- OpenCode server/attach mode (`opencode serve`, long-lived sessions); one-shot `run` only.
- Session continuity across Harvey calls (`--continue` / `--session`); each call is independent, like Claude today.
- Making OpenCode the default provider.
- Changing Codex's Windows refusal or Claude's behavior.
- OpenCode plugin/MCP management; Harvey prompts stay tool-free (`--auto` is not passed; permissions-denied errors surface as transient failures).
- Real-time OpenCode cost import from `opencode stats` into Harvey's usage DB.
- Upstream PR to ethanplusai/harvey (branch stays local until the owner chooses).

## Further Notes

- OpenCode CLI on this machine: v1.19.4, `run --format json` emits raw JSON events; `-m` takes `provider/model`; `--variant` exists for reasoning effort but is unused in v1.
- Operator's intended models: MiMo v2.5 (and other MiMo variants) and cheap DeepSeek models reachable through OpenCode's providers — all pass through the free-form `provider/model` config unchanged; Harvey never hardcodes a model list.
- The Claude one-shot loop in the brain module is the template; Codex's 1,500-line adapter is explicitly not the template.
- Windows process kill semantics differ from POSIX; reuse the existing kill path and cover it in the timeout test.
- Exact JSON event schema for final text/tokens must be confirmed with one live `opencode run --format json` during implementation (cost: one tiny prompt) before locking the parser tests' canned fixtures.
