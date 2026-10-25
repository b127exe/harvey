# 03: CLI, setup wizard, train surface

**What to build:** An operator can select and verify OpenCode entirely from Harvey's CLI: the setup wizard offers opencode (PATH + auth check, free-form model prompt, writes `brain:` to harvey.yaml), `harvey status --check` reports OpenCode readiness via preflight, `harvey status`/`harvey usage` show OpenCode call counts and labels, and `harvey train --provider opencode` is accepted.

**Blocked by:** 02 (brain dispatch + usage migration).

**Status:** resolved

- [x] Setup wizard provider menu includes opencode; prerequisite check verifies the `opencode` binary; model asked free-form and saved to harvey.yaml; summary label correct
- [x] `harvey status --check` with opencode runs adapter preflight and prints a ready/not-ready message
- [x] `harvey status` shows an OpenCode calls-today counter
- [x] `harvey usage` has an opencode branch: call counts shown, subscription gauges marked unavailable
- [x] `harvey train --provider opencode` accepted; switching providers still drops the other provider's model correctly
- [x] Provider suite tests cover the new menu/choices/labels (stubbed adapter, no real CLI)

## Comments

- `Brain.preflight()` gained an opencode branch (version + credentials, no prompt) with the same sticky-pause/recheck behaviour as Codex; the stored-pause restore was extracted into a shared helper used by both branches.
- `_test_claude` renamed `_test_brain` — it now exercises all three providers.
- Review fixes: persistent-kinds set form, fingerprint annotation, `--provider` choices derived from `BRAIN_PROVIDERS`, codex→opencode model-drop + yaml round-trip tests added.
