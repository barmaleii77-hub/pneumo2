# Project KB audit 2026-04-20

## Scope

Проверен текущий `main` после синхронизации с `origin/main`:

- база знаний и порядок источников: `00_READ_FIRST__ABSOLUTE_LAW.md`, `01_PARAMETER_REGISTRY.md`, `DATA_CONTRACT_UNIFIED_KEYS.md`, `docs/00_PROJECT_KNOWLEDGE_BASE.md`, `docs/PROJECT_SOURCES.md`;
- GUI canon: `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`, `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`;
- imported GUI/KB layers: `docs/context/gui_spec_imports/v3/*`, `docs/context/gui_spec_imports/v13_ring_editor_migration/*`, `docs/context/gui_spec_imports/v37_github_kb_supplement/*`;
- runtime alignment points: `pneumo_solver_ui/desktop_spec_shell/*`, `pneumo_solver_ui/desktop_input_model.py`, optimization StageRunner UI;
- contract tests.

## Source priority observed

Рабочий порядок источников подтвержден:

1. `00_READ_FIRST__ABSOLUTE_LAW.md`, `01_PARAMETER_REGISTRY.md`, `DATA_CONTRACT_UNIFIED_KEYS.md`.
2. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`.
3. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`.
4. `docs/context/gui_spec_imports/v37_github_kb_supplement/*` как successor KB/TZ/spec supplement, но не runtime-closure proof.
5. `docs/context/gui_spec_imports/v3/*` как active detailed runtime-readable GUI catalog layer.
6. `docs/context/gui_spec_imports/v13_ring_editor_migration/*` и `v12_design_recovery/*` как specialized/historical layers.
7. `docs/gui_chat_prompts/*` как implementation prompts, не канон.

## Findings

### Closed in this step

- Full contract suite was failing in six places before the fix: five `desktop_input_editor` contract regressions and one StageRunner wording contract.
- `desktop_input_model.py` now presents mass context inside the engineering `Механика` summary card, keeps `corner_loads_mode` visible from the static setup route, and surfaces the internal-step limit under `Справочные данные` where the GUI contract expects reference/limit issues.
- `optimization_stage_runner_config_ui.py` now exposes the required StageRunner operator label: `StageRunner: warm-start, influence и staged seed/promotion`.

### Still open

- `v37_github_kb_supplement` is correctly imported and referenced, but it explicitly declares `runtime_closure_proof: false`; runtime still uses `ACTIVE_GUI_SPEC_IMPORT_VERSION = "v3"`.
- Several visible shell commands still lack complete `automation_id` / `tooltip_id` bindings. This is the next GUI-spec metadata gap to close.
- v37 open gaps remain intentionally open and must not be presented as closed: producer-side solver-point truth, cylinder packaging passport, measured performance/viewport gating, Windows visual/runtime acceptance.
- `docs/15_CHAT_KNOWLEDGE_BASE.json` is older than the latest audit/import work and should be refreshed from the current chat/audit decisions.

## Validation

- Targeted failing set:
  - `pytest -q --timeout=45 tests/test_desktop_input_editor_contract.py tests/test_r31ce_optimization_page_stage_runner_contract.py`
  - Result: `25 passed in 1.46s`
- Full tracked contract set:
  - `pytest -q --timeout=45 tests/test_*contract*.py`
  - Result: `853 passed in 55.56s`

## Recommended next step

Close the GUI-spec metadata gap in `desktop_spec_shell`:

- add/derive stable `automation_id` and `tooltip_id` for every visible non-legacy command;
- ensure diagnostics hosted actions and workspace open commands are fully catalog-bound;
- add a contract test that fails on missing command metadata instead of checking only selected commands.
