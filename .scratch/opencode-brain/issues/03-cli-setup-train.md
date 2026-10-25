# 03: CLI, setup wizard, train surface

**What to build:** An operator can select and verify OpenCode entirely from Harvey's CLI: the setup wizard offers opencode (PATH + auth check, free-form model prompt, writes `brain:` to harvey.yaml), `harvey status --check` reports OpenCode readiness via preflight, `harvey status`/`harvey usage` show OpenCode call counts and labels, and `harvey train --provider opencode` is accepted.

**Blocked by:** 02 (brain dispatch + usage migration).

**Status:** ready-for-agent

- [ ] Setup wizard provider menu includes opencode; prerequisite check verifies the `opencode` binary; model asked free-form and saved to harvey.yaml; summary label correct
- [ ] `harvey status --check` with opencode runs adapter preflight and prints a ready/not-ready message
- [ ] `harvey status` shows an OpenCode calls-today counter
- [ ] `harvey usage` has an opencode branch: call counts shown, subscription gauges marked unavailable
- [ ] `harvey train --provider opencode` accepted; switching providers still drops the other provider's model correctly
- [ ] Provider suite tests cover the new menu/choices/labels (stubbed adapter, no real CLI)
