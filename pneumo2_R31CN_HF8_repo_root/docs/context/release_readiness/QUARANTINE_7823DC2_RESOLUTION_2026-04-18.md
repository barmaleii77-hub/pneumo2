# Quarantine 7823dc2 Resolution 2026-04-18

Purpose: record how the local quarantine branch
`codex/quarantine-mixed-gui-dirty-20260418` and commit `7823dc2` were resolved.

This is an integration note, not a final runtime closure claim for the affected
GUI domains.

## Source

- quarantine branch: `codex/quarantine-mixed-gui-dirty-20260418`
- quarantine commit: `7823dc2 chore: quarantine mixed gui dirty tree`
- integration target: `codex/work`
- integration method: `git cherry-pick --no-commit 7823dc2`

The quarantine branch was not merged as a branch because it was based before
the branch/tree recovery documentation. A branch merge would have reintroduced
stale branch-tree state. Cherry-pick applied only the actual code/test/doc
delta from `7823dc2^..7823dc2`.

## Integrated Scope

| lane | integrated paths | intent |
| --- | --- | --- |
| Main Shell | `START_PNEUMO_APP.py`, `desktop_qt_shell/main_window.py`, `desktop_qt_shell/runtime_proof.py`, shell tests | make the classic Desktop Main Shell the launcher target and expose all launchable GUI modules through browser/menu/toolbar/search coverage |
| Input Data | `desktop_input_model.py`, `desktop_input_graphics.py`, `tools/desktop_input_editor.py`, input tests | show source/state markers, rename display title `Численные настройки` to `Расчётные настройки`, expose WS-INPUTS snapshot/folder actions |
| Desktop Mnemo | `desktop_mnemo/app.py`, `desktop_mnemo/runtime_proof.py`, Mnemo tests and acceptance note | stop local timers on close, prove close-return and unavailable truth state, record manual Windows visual boundaries |
| Optimizer/Results | `desktop_optimizer_*`, `desktop_results_*`, optimizer/results tools and tests | surface selected-run identity, block unsafe resume, expose optimizer selected-run contract in Results Center evidence |

## Validation

Quarantine branch check:

```powershell
python -m pytest tests/test_desktop_input_editor_contract.py tests/test_desktop_main_shell_qt_contract.py tests/test_desktop_mnemo_runtime_proof.py tests/test_desktop_mnemo_window_contract.py tests/test_desktop_optimizer_center_contract.py tests/test_test_center_results_center_contract.py tests/test_web_launcher_desktop_bridge_contract.py -q
```

Result:

- `101 passed`
- expected Qt deprecation warnings in `desktop_mnemo/app.py`

Current `codex/work` after cherry-pick:

```powershell
python -m pytest tests/test_desktop_input_editor_contract.py tests/test_desktop_main_shell_qt_contract.py tests/test_desktop_mnemo_runtime_proof.py tests/test_desktop_mnemo_window_contract.py tests/test_desktop_optimizer_center_contract.py tests/test_test_center_results_center_contract.py tests/test_web_launcher_desktop_bridge_contract.py tests/test_gui_spec_docs_contract.py tests/test_ui_text_no_mojibake_contract.py -q
```

Result:

- `131 passed`
- expected Qt deprecation warnings in `desktop_mnemo/app.py`

## Post-Resolution Branch Policy

After the integration commit lands on `codex/work`, the local quarantine branch
is no longer a required working branch and can be deleted locally.

Future work must continue from clean `origin/codex/work` and the current prompt
pack:

- `docs/gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md`

Do not recreate the quarantine branch unless a new explicit rescue snapshot is
needed.

## Non-Claims

- This does not close final Windows visual acceptance.
- This does not close long-running Mnemo stability, Snap Layouts,
  second-monitor or mixed-DPI checks.
- This does not close producer truth, geometry, packaging, Animator, Compare,
  diagnostics/SEND or open gaps `OG-001` through `OG-006`.
- This does not make WEB a target platform; the WEB launcher remains a bridge
  to the desktop main shell.

