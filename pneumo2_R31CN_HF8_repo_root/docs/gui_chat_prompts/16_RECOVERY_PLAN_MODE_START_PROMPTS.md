# Post-Quarantine V38 Visual Plan-Mode Start Prompts

Purpose: self-contained starter prompts for the same 10 parallel chats after
the branch/tree recovery pass, quarantine `7823dc2` resolution and V38 KB
import of 2026-04-18. This version adds mandatory V38 visual acceptance,
optimized user-pipeline checks and V38 ambiguity-audit checks for every GUI
lane.

Use this file instead of `15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md` for new
chat starts. It assumes that `codex/work` is clean, old local worktree sprawl
has been removed, quarantine commit `7823dc2` has been integrated into
`codex/work` by cherry-pick and the local quarantine branch has been deleted.

## Global First-Run Rule

Every new chat starts in Plan mode.

Plan mode means:

- inspect only;
- do not edit files;
- do not stage, commit or push;
- do not create, delete or move branches or worktrees;
- do not run bulk cleanup commands;
- do not recreate, merge, rebase or cherry-pick the resolved quarantine branch;
- report current branch, dirty files, owned files, forbidden files, proposed
  minimal patch, tests and evidence boundaries;
- wait for user confirmation before implementation.

Every chat must start from `origin/codex/work`, not from `main` and not from
any historical local branch. If the current worktree is dirty, the chat must
report the dirty paths and stop before implementation.

The old quarantine branch is resolved. Do not look for it as a working source.
If historical context is needed, read:

- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md`

The integrated baseline from `7823dc2` is now part of `codex/work` and covers:

- Main Shell launch surface and all-launchable-GUI coverage.
- Input Data source/state markers and `Расчётные настройки` display title.
- Desktop Mnemo close/runtime proof and unavailable truth-state evidence.
- Optimizer/Results selected-run identity, resume safety and selected-run
  contract evidence.

Global prohibitions:

- do not expand WEB;
- do not duplicate `desktop_animator`, `qt_compare_viewer` or `desktop_mnemo`;
- do not invent parameters, aliases or silent remaps;
- do not hide open gaps as closed;
- do not introduce mojibake or broken Russian text;
- do not touch another lane's owned files without explicit coordination.
- do not expose service metadata as primary user information: migration state,
  runtime toolkit, implementation phase, internal module names and managed
  launcher mode belong in logs/evidence, not in the operator surface;
- do not invent local labels outside V38 vocabulary; for example the input
  workspace is `Исходные данные`, not ad-hoc "machine data" wording;
- do not preserve extra click-through navigation. V38 tree/search/selection
  sync is the required user path.

Mandatory V38 visual and pipeline gate:

- every lane must visually open its owned GUI window or workspace on Windows
  or Qt offscreen when real Windows is unavailable;
- every lane must compare the visible window against V38 `GUI_SPEC.yaml`,
  `WORKSPACE_CONTRACT_MATRIX.csv`, `ACCEPTANCE_MATRIX.csv` and
  `PIPELINE_OPTIMIZED.dot`;
- every lane must report whether the visible flow follows the optimized graph:
  `SHELL -> PROJECT -> INPUTS -> RING -> SUITE -> BASELINE -> OPT -> ANALYSIS`
  and then `ANALYSIS -> ANIMATOR` / `ANALYSIS -> DIAGNOSTICS`;
- tree/search/selection sync from `WS-SHELL` must be treated as navigation, not
  as a reason to require an extra navigation button;
- any mandatory intermediate navigation button is a V38 blocker: remove it or replace it
  with direct selection sync before claiming acceptance;
- visible service-status dashboards are V38 blockers: replace them with
  operator-facing readiness, source, artifact, warning and next-action text;
- screenshots, runtime proof, or a written visual checklist are required as
  evidence; unit tests alone are not enough for GUI acceptance.

Required first-read documents for every lane:

- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/ACCEPTANCE_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PIPELINE_OPTIMIZED.dot`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v33_connector_reconciled/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v37_github_kb_supplement/README.md` only as predecessor provenance when needed.

Required Plan-mode answer shape:

1. Current branch/worktree state.
2. Files owned by this lane.
3. Files explicitly forbidden for this lane.
4. Relevant KB requirements and open gaps.
5. Which post-quarantine baseline behaviors this lane must preserve.
6. V38 visual mismatch list: visible labels, panels, commands, status bars,
   navigation, service-jargon leaks and operator information quality.
7. Optimized pipeline mismatch list: unnecessary steps, missing direct
   navigation, missing handoff, broken `tree/search/selection sync`.
8. Minimal implementation plan after confirmation.
9. Tests and manual Windows checks.
10. Evidence artifacts to update or create.

## 1. Главное Окно И Поверхность Запуска

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Главное окно и поверхность запуска.

Цель:
Собрать понятное классическое Windows GUI главное окно: верхнее меню, единый список запуска всех GUI-модулей, рабочая область, status/progress strip, runtime-proof запуска и нормальная навигация оператора. WEB не развивать, допускается только containment/bridge для вызова desktop GUI.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`
- `git branch --format="%(refname:short) %(objectname:short) %(upstream:short)"`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/01_MAIN_WINDOW.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/START_PNEUMO_APP.py`
- `pneumo2_R31CN_HF8_repo_root/START_DESKTOP_MAIN_SHELL.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_qt_shell/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell_qt.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/launch_ui.py`
- shell-focused tests: `tests/test_desktop_main_shell_qt_contract.py`, `tests/test_desktop_main_shell_contract.py`, `tests/test_desktop_shell_parity_contract.py`, `tests/test_home_desktop_gui_launcher_contract.py`, `tests/test_web_launcher_desktop_bridge_contract.py`

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo_solver_ui/desktop_mnemo/*`
- optimizer/results internals
- diagnostics/SEND producer internals
- model/solver files

Post-resolution baseline:
The `7823dc2` shell work is already integrated. Preserve `Desktop Main Shell` as the launch target, `desktop_main_shell_qt.log` as the launcher log, and all-launchable-GUI coverage through browser, menu, toolbar and command search. Do not reintroduce `desktop_gui_spec_shell` as the primary launcher.

Mandatory V38 visual/pipeline check:
Open the main shell and prove it behaves like `WS-SHELL` from V38: menu/search/tree/inspector/status must be operator-facing, not a service-status dashboard. Check `PIPELINE_OPTIMIZED.dot`: shell selection must synchronize directly to project/input/ring/suite/baseline/optimization/analysis/animator/diagnostics surfaces. If the shell still depends on a mandatory intermediate navigation button, remove it or replace it with direct selection sync before claiming V38 acceptance.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_main_shell_qt_contract.py tests/test_desktop_main_shell_contract.py tests/test_desktop_shell_parity_contract.py tests/test_home_desktop_gui_launcher_contract.py tests/test_web_launcher_desktop_bridge_contract.py -q`
- manual Windows visible startup if runtime behavior changes.
```

## 2. Ввод Исходных Данных

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Ввод исходных данных.

Цель:
Сделать desktop input window удобным и понятным: секции геометрия, пневматика, механика, компоненты, справочные данные и настройки расчета; слайдеры и числовые поля; единицы; source markers; dirty/current state; frozen snapshot handoff. WEB не расширять.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/02_INPUT_DATA.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_CATALOG.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_VISIBILITY_MATRIX.csv`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_graphics.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_suite_snapshot.py` only if handoff snapshot requires it
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_editor_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_graphics_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_suite_snapshot.py` only for handoff checks

Forbidden without explicit coordination:
- main shell launcher behavior except adapter registration requests
- ring editor internals
- optimizer/results internals
- model/solver files and parameter registry changes unless the plan explicitly proves a canonical-key update is required

Post-resolution baseline:
The `7823dc2` input work is already integrated. Preserve source/state markers, `Расчётные настройки` as the display title for numerical calculation settings, and WS-INPUTS snapshot/folder actions. Do not rename canonical section keys in persisted handoff data.

Mandatory V38 visual/pipeline check:
Open the input window and verify V38 `WS-INPUTS`: geometry, pneumatics, mechanics, components, references and calculation settings must be visible as meaningful operator clusters with sliders/units/source markers. The visible flow must be `PROJECT -> INPUTS -> RING` via saved `inputs_snapshot.json`; cluster selection must lead directly to editing without an extra navigation action.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_input_editor_contract.py tests/test_desktop_input_graphics_contract.py tests/test_desktop_suite_snapshot.py -q`
- manual Windows smoke for scrolling, sliders, Russian labels and no mojibake.
```

## 3. Desktop Mnemo

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Desktop Mnemo.

Цель:
Довести Desktop Mnemo как отдельное специализированное окно: правдивая пневмосхема, source markers, unavailable states, runtime proof, нормальное открытие из shell и evidence для diagnostics/SEND. Не дублировать Mnemo внутри shell и не переписывать Animator/Compare.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/06_DESKTOP_MNEMO.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/08_DesktopMnemo.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py` only for legacy launcher/reference containment
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_mnemo_*.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_pneumo_scheme_mnemo_cache_resource_contract.py`

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- shell internals except small adapter/launcher requests
- diagnostics/SEND internals except evidence-manifest registration requests

Post-resolution baseline:
The `7823dc2` Mnemo work is already integrated. Preserve close-time timer shutdown, unavailable truth-state visibility, runtime-proof close checks and the acceptance note boundaries. Treat `DESKTOP_MNEMO_WINDOWS_ACCEPTANCE_2026-04-18.md` as automated evidence plus manual-check TODOs, not final Windows visual closure.

Mandatory V38 visual/pipeline check:
Open Desktop Mnemo and verify it is a specialized truth/unavailable-state graphics surface, not a generic service-status panel. It must be reachable from shell selection/search without duplicating Mnemo inside shell. Check the optimized graph boundary: Mnemo is diagnostic/visual evidence consumer territory and must not intercept `INPUTS -> RING -> SUITE` authoring flow.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_mnemo_runtime_proof.py tests/test_desktop_mnemo_window_contract.py tests/test_desktop_mnemo_dataset_contract.py tests/test_desktop_mnemo_launcher_contract.py tests/test_desktop_mnemo_settings_bridge_contract.py tests/test_desktop_mnemo_snapshot_contract.py -q`
- manual visible startup and close behavior on Windows.
```

## 4. Compare Viewer

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Compare Viewer.

Цель:
Довести Compare Viewer как отдельное специализированное окно: загрузка runs/bundles, objective integrity, baseline/source hash, mismatch banners, session autoload, dock/layout acceptance, real-bundle smoke. Не дублировать viewer в shell.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/05_COMPARE_VIEWER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_contract.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_npz_web.py` only for legacy reference/containment
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/06_CompareViewer_QT.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/07_CompareNPZ_QT.py`
- compare-focused tests: `tests/test_qt_compare_*.py`, `tests/test_r64_qt_compare_viewer_workspace_layout_runtime.py`, `tests/test_r65_qt_compare_viewer_real_bundle_runtime_smoke.py`

Forbidden without explicit coordination:
- Desktop Animator internals
- optimizer objective producer internals
- shell internals except adapter registration requests
- diagnostics/SEND packaging internals

Post-resolution baseline:
No Compare Viewer code came from `7823dc2`. Start from current `codex/work` and coordinate only through explicit handoff artifacts such as selected-run context sidecars, objective hashes and diagnostics evidence.

Mandatory V38 visual/pipeline check:
Open Compare Viewer and verify it behaves as the `WS-ANALYSIS` compare/objective surface: selected run, baseline/source hashes, mismatch banners and compare contract must be immediately understandable. Check optimized graph compliance: `OPT -> ANALYSIS` must use `selected_run_contract.json`, then analysis may hand off to Animator and Diagnostics; shell navigation must not insert extra intermediate clicks before comparison.

Expected tests after implementation approval:
- `python -m pytest tests/test_qt_compare_viewer_compare_contract.py tests/test_qt_compare_viewer_dock_object_names.py tests/test_qt_compare_viewer_session_autoload_source.py tests/test_qt_compare_offline_npz_anim_diagnostics.py tests/test_r64_qt_compare_viewer_workspace_layout_runtime.py tests/test_r65_qt_compare_viewer_real_bundle_runtime_smoke.py -q`
- manual real-bundle open and mismatch-banner smoke if runtime behavior changes.
```

## 5. Desktop Animator

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Desktop Animator.

Цель:
Довести Desktop Animator как отдельное специализированное окно без подмены данных: truth contract, authored geometry, playback stability, GL/runtime evidence, scene quality, diagnostics visibility and real-bundle behavior. Не превращать Animator в общий shell и не переносить туда чужие workflows.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/07_DESKTOP_ANIMATOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/anim_export_contract.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/anim_export_meta.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/mech_anim_fallback.py` only when truth policy requires it
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/npz_anim_diagnostics.py`
- animator-focused tests: `tests/test_*anim*.py`, `tests/test_r*_animator_*.py`, `tests/test_v32_desktop_animator_truth_contract.py`

Forbidden without explicit coordination:
- `pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo_solver_ui/desktop_mnemo/*`
- shell internals except launcher adapter requests
- model/solver changes unless the plan proves a producer-truth bug and updates evidence

Post-resolution baseline:
No Desktop Animator code came from `7823dc2`. Start from current `codex/work`; preserve shell discoverability without moving Animator rendering or truth logic into shell or results modules.

Mandatory V38 visual/pipeline check:
Open Desktop Animator and verify V38 `WS-ANIMATOR`: truthful graphics consumer, analysis context, artifacts, source markers and unavailable states must be visually obvious. Check optimized graph compliance: Animator is reached from `ANALYSIS -> ANIMATOR`, not by inventing geometry or by forcing the user through unrelated navigation.

Expected tests after implementation approval:
- choose a focused animator subset that matches the patch;
- include `python -m pytest tests/test_v32_desktop_animator_truth_contract.py tests/test_desktop_animator_page_contract.py tests/test_desktop_animator_startup_docked.py -q` unless the plan justifies a narrower set;
- manual real-bundle runtime smoke for GL/playback changes.
```

## 6. Optimizer And Results Center

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Оптимизатор и центр результатов.

Цель:
Собрать понятный desktop optimizer/results workflow: все настройки оптимизации, objective/hard gates, baseline/source mismatch, resume/history, run contract persistence, results/test validation center, evidence panels and handoff to Compare/Diagnostics. Не подменять Compare Viewer и не встраивать Animator.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/08_OPTIMIZER_CENTER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v12_design_recovery/optimization_control_plane_contract_v12.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_panels.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_tabs/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_optimizer_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_results_center.py`
- optimizer/results tests: `tests/test_desktop_optimizer_center_contract.py`, `tests/test_test_center_results_center_contract.py`, `tests/test_optimization_*.py`, `tests/test_r31cw_optimization_run_history_objective_contract.py`

Forbidden without explicit coordination:
- `pneumo_solver_ui/qt_compare_viewer.py`
- Desktop Animator internals
- diagnostics/SEND packaging internals except evidence handoff requests
- input/ring/run-setup source editors except explicit handoff contracts

Post-resolution baseline:
The `7823dc2` optimizer/results work is already integrated. Preserve selected-run identity, resume preflight blocking for mismatched history runs, selected optimizer run contract evidence in Results Center and latest optimizer pointer surfacing.

Mandatory V38 visual/pipeline check:
Open Optimizer and Results Center and verify V38 `WS-OPTIMIZATION` / `WS-ANALYSIS`: objective contract, hard gates, baseline, selected-run identity, run history and results evidence must be visible as workflow information, not hidden in service-status labels. Check optimized graph compliance: `BASELINE -> OPT -> ANALYSIS` must be the main path, and selecting a run must create/consume `selected_run_contract.json` without an extra navigation step.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_optimizer_center_contract.py tests/test_test_center_results_center_contract.py tests/test_optimization_objective_contract.py tests/test_optimization_resume_run_dir.py tests/test_optimization_staged_resume_run_dir.py tests/test_r31cw_optimization_run_history_objective_contract.py -q`
```

## 7. Diagnostics And SEND Bundle

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Diagnostics и SEND Bundle.

Цель:
Сделать diagnostics/send-bundle flow первым классом desktop GUI: one-click diagnostics, health report, send bundle creation/validation, evidence manifest, latest pointers, postmortem watchdog and honest producer gaps. Не закрывать open gaps без реальных artifacts.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/diagnostics_entrypoint.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/diagnostics_unified.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_diagnostics_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/make_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/inspect_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_bundle_evidence.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/validate_send_bundle.py`
- diagnostics/send tests: `tests/test_desktop_diagnostics_center_contract.py`, `tests/test_v32_diagnostics_send_bundle_evidence.py`, `tests/test_run_full_diagnostics_tool.py`, `tests/test_health_report_inspect_send_bundle_anim_diagnostics.py`

Forbidden without explicit coordination:
- producer/model code that should generate missing artifacts;
- Desktop Animator rendering internals;
- Compare Viewer internals;
- optimizer/results UI except evidence handoff requests.

Post-resolution baseline:
The quarantine branch is resolved. Diagnostics should consume current `codex/work` evidence surfaces, including Mnemo runtime proof visibility and optimizer selected-run contract artifacts where relevant, without claiming closure for producer-owned gaps.

Mandatory V38 visual/pipeline check:
Open Diagnostics/SEND Bundle and verify V38 `WS-DIAGNOSTICS`: evidence manifest, SEND bundle, health, warnings and missing producer artifacts must be operator-readable. Check optimized graph compliance: Diagnostics is always visible from shell and receives `ANALYSIS -> DIAGNOSTICS` plus `ANIMATOR -> DIAGNOSTICS`; do not hide diagnostics behind extra navigation.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_diagnostics_center_contract.py tests/test_v32_diagnostics_send_bundle_evidence.py tests/test_run_full_diagnostics_tool.py tests/test_health_report_inspect_send_bundle_anim_diagnostics.py tests/test_diagnostics_text_encoding_contract.py -q`
```

## 8. Geometry, Catalogs And Producer Truth

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Геометрия, каталоги и producer truth.

Цель:
Собрать desktop reference center for geometry/catalogs and producer truth: source-of-truth geometry, catalog-aware packaging, cylinder/wheel/suspension evidence, geometry acceptance, anim_latest/source metadata and no invented viewer geometry.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/11_GEOMETRY_REFERENCE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_geometry_reference_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/camozzi_catalog_ui.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/geometry_acceptance_contract.py`
- producer truth helpers only when the plan proves ownership of source/export metadata
- geometry/catalog tests: `tests/test_desktop_geometry_reference_center_contract.py`, `tests/test_geometry_acceptance_release_gate.py`, `tests/test_geometry_acceptance_web_and_bundle.py`, `tests/test_active_generators_solver_points_canon.py`

Forbidden without explicit coordination:
- Desktop Animator rendering implementation except truth-contract handoff;
- model/solver equations unless this lane explicitly proves the producer bug;
- Compare Viewer UI;
- shell UI except adapter registration requests.

Post-resolution baseline:
No geometry/catalog producer code came from `7823dc2`. Start from current `codex/work` and preserve strict source-of-truth geometry and no invented viewer geometry.

Mandatory V38 visual/pipeline check:
Open Geometry/Catalogs/Reference and verify V38 source-of-truth behavior: catalog values, geometry references, producer status and unavailable states must be visible without implying runtime closure. Check optimized graph compliance: geometry/reference supports INPUTS, BASELINE, OPT and ANIMATOR truth, but must not insert an extra mandatory step into the core user pipeline.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_geometry_reference_center_contract.py tests/test_geometry_acceptance_release_gate.py tests/test_geometry_acceptance_web_and_bundle.py tests/test_active_generators_solver_points_canon.py -q`
```

## 9. Engineering Analysis, Calibration And Influence

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Engineering Analysis, Calibration и Influence.

Цель:
Собрать desktop analysis/calibration/influence center: calibration pipelines, influence reports, sensitivity/uncertainty, analysis evidence, handoff to optimizer/results and honest status for runtime/data gaps.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/12_ENGINEERING_ANALYSIS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/param_influence_ui.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/calibration/*`
- engineering/calibration tests: `tests/test_desktop_engineering_analysis_contract.py`, `tests/test_desktop_engineering_analysis_center_contract.py`, `tests/test_static_trim_pressure_*.py`

Forbidden without explicit coordination:
- optimizer UI except handoff contract requests;
- model/solver core unless the plan proves an analysis truth bug;
- Desktop Animator/Compare/Mnemo surfaces;
- diagnostics/SEND packaging except evidence handoff requests.

Post-resolution baseline:
No engineering/calibration code came from `7823dc2`, but the main shell now exposes the engineering analysis center in all launch surfaces. Preserve that discoverability and coordinate analysis handoff through optimizer/results evidence, not shell duplication.

Mandatory V38 visual/pipeline check:
Open Engineering Analysis/Calibration/Influence and verify V38 analysis workspace behavior: calibration data, influence, uncertainty/sensitivity, selected-run context and handoff status must be visible as engineering information. Check optimized graph compliance: analysis consumes selected run and compare context, then hands off to Animator/Diagnostics; shell navigation must not become a required analysis step.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_engineering_analysis_contract.py tests/test_desktop_engineering_analysis_center_contract.py tests/test_static_trim_pressure_p0_bootstrap.py tests/test_static_trim_pressure_trim_targets.py -q`
```

## 10. Ring Editor And Run Setup Handoff

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Редактор кольца и настройка расчета.

Цель:
Собрать desktop ring editor/generator and run setup handoff: canonical ring scenario source, segment semantics, validation, suite snapshot, run settings, no free-form spec drift, handoff to optimizer/results and diagnostics.

Стартовые команды только для чтения:
- `git fetch --all --prune`
- `git status --short --branch`

Сначала прочитай общие документы из Global First-Run Rule, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/03_RUN_SETUP.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/04_RING_EDITOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_ring_editor_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_ring_editor_panels.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_ring_editor_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_run_setup_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_run_setup_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_run_setup_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_generator.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_scenario_ring.py`
- ring/run setup tests: `tests/test_desktop_ring_editor_contract.py`, `tests/test_desktop_run_setup_center_contract.py`, `tests/test_desktop_run_setup_modules.py`, `tests/test_r33_ring_sine_input_semantics.py`, `tests/test_ui_scenario_ring_no_free_spec.py`

Forbidden without explicit coordination:
- input editor source UI except frozen input handoff requests;
- optimizer/results runtime except suite consumer handoff requests;
- Desktop Animator/Compare/Mnemo internals;
- model/solver files unless canonical scenario semantics require a contract update.

Post-resolution baseline:
No ring/run setup code came from `7823dc2`. Start from current `codex/work`; preserve input handoff semantics and do not rename persisted canonical scenario or suite keys while improving desktop workflow.

Mandatory V38 visual/pipeline check:
Open Ring Editor and Run Setup and verify V38 `WS-RING` / `WS-SUITE`: ring editor is the sole scenario source, canonical export set and validated suite snapshot must be visible and understandable. Check optimized graph compliance: `INPUTS -> RING -> SUITE -> BASELINE` must be a direct authoring path; tree selection must lead directly to editing/suite validation without an extra navigation action.

Expected tests after implementation approval:
- `python -m pytest tests/test_desktop_ring_editor_contract.py tests/test_desktop_run_setup_center_contract.py tests/test_desktop_run_setup_modules.py tests/test_r33_ring_sine_input_semantics.py tests/test_ui_scenario_ring_no_free_spec.py -q`
```
