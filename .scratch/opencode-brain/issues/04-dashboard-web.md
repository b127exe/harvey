# 04: Dashboard + web UI

**What to build:** The local dashboard reflects OpenCode as the active provider: pipeline stats and the usage API include the OpenCode call counter, the quota card shows an explicit unavailable state instead of fake gauges, and the UI labels/FAQ mention OpenCode alongside Claude and Codex.

**Blocked by:** 02 (brain dispatch + usage migration).

**Status:** ready-for-agent

- [ ] Dashboard stats endpoints include the opencode call count
- [ ] Usage API returns OpenCode calls with quota marked unavailable
- [ ] Frontend renders an OpenCode call chip and shows "unavailable" on the quota card when provider is opencode
- [ ] Dashboard FAQ includes a short OpenCode note (parallel to the Codex note)
- [ ] Existing claude/codex dashboard tests still pass; new assertions cover the opencode shapes
