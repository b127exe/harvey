# 04: Dashboard + web UI

**What to build:** The local dashboard reflects OpenCode as the active provider: pipeline stats and the usage API include the OpenCode call counter, the quota card shows an explicit unavailable state instead of fake gauges, and the UI labels/FAQ mention OpenCode alongside Claude and Codex.

**Blocked by:** 02 (brain dispatch + usage migration).

**Status:** resolved

- [x] Dashboard stats endpoints include the opencode call count
- [x] Usage API returns OpenCode calls with quota marked unavailable
- [x] Frontend renders an OpenCode call chip and shows "unavailable" on the quota card when provider is opencode
- [x] Dashboard FAQ includes a short OpenCode note (parallel to the Codex note)
- [x] Existing claude/codex dashboard tests still pass; new assertions cover the opencode shapes

## Comments

- `brainCallChips` rewritten around a provider→name map (active provider's chip always shown, others when nonzero) — preserves claude/codex behaviour exactly, adds the paused-provider name for OpenCode.
- Quota card: per-provider title + unavailable message; OpenCode's message points at `opencode stats` and skips the "budgets count Harvey's own calls" tail (Harvey never reads OpenCode quota, so "until it can" would be wrong).
- Kept display-name maps inside each JS function: the test harness extracts single functions, so a shared top-level const would break it.
