# Post-Acceptance V38 Plan-Mode Start Prompts

Purpose: current starter prompt pack for parallel GUI chats after the 10 V38
GUI chat handoffs were accepted into `codex/work`, temporary worktrees were
removed, local chat branches were cleaned up and `origin/codex/work` was
updated to `ed9c4cd` on 2026-04-18.

Use this file instead of `16_RECOVERY_PLAN_MODE_START_PROMPTS.md` for all new
parallel GUI chats. The previous prompt packs are historical context only.

## Current Baseline

The current branch for new work is `codex/work`.

Expected starting state:

- local `codex/work` equals `origin/codex/work`;
- only the main worktree `C:/Users/Admin/Documents/GitHub/pneumo2` exists;
- temporary chat worktrees are gone;
- old local chat branches are gone;
- the V38 import layer is current;
- V37 is predecessor provenance only;
- accepted GUI handoffs are already integrated and must not be reimplemented
  from scratch.

Accepted handoffs now in `codex/work`:

- main shell launch surface and V38 pipeline surfaces;
- input data source/state markers and calculation settings display;
- ring scenario editor plus run setup handoff;
- Compare Viewer V38 compare/session behavior;
- Desktop Mnemo runtime/acceptance evidence;
- Desktop Animator truth/runtime and cylinder render policy;
- optimizer/results workflow handoff;
- diagnostics/send bundle honest evidence;
- geometry/catalogs/reference producer truth;
- engineering analysis/calibration/influence evidence status.

## Global First-Run Rule

Every new chat starts in Plan mode.

Plan mode means:

- inspect only;
- do not edit files;
- do not stage, commit or push;
- do not create, delete or move branches or worktrees;
- do not run bulk cleanup commands;
- do not recreate historical chat branches;
- do not cherry-pick old handoff commits;
- report current branch, HEAD, dirty paths, owned files, forbidden files,
  relevant V38 requirements, visible GUI mismatches, optimized-pipeline
  mismatches, proposed minimal patch and tests;
- wait for explicit user approval before implementation.

Required first commands:

```powershell
git fetch --all --prune
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/codex/work
git worktree list --porcelain
git branch -vv --all
```

If `HEAD` differs from `origin/codex/work`, or the worktree is dirty, stop and
report before planning implementation.

## Global Required Reading

Read these before lane-specific files:

- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/13_CHAT_REQUIREMENTS_LOG.md`
- `pneumo2_R31CN_HF8_repo_root/docs/14_CHAT_PLANS_LOG.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/ACCEPTANCE_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PIPELINE_OPTIMIZED.dot`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/REPO_OPEN_GAPS_TO_KEEP_OPEN.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v37_github_kb_supplement/README.md` only as predecessor provenance when needed.

## Global Prohibitions

- Do not expand WEB UI. WEB may keep only temporary launch buttons for desktop
  modules until migration is complete.
- Do not duplicate `desktop_animator`, `qt_compare_viewer` or `desktop_mnemo`.
- Do not expose implementation metadata as primary operator information.
- Do not show phrases like `Статус миграции`, `Открыть выбранный этап`,
  `Данные машины`, runtime toolkit names, internal module names or managed mode
  labels in the operator surface.
- Do not invent new user-facing labels outside the V38 vocabulary.
- Do not hide open gaps as closed.
- Do not invent parameters, aliases or silent remaps.
- Do not touch another lane's owned files without explicit coordination.
- Do not claim GUI acceptance from unit tests alone.

## Mandatory V38 Gate For Every Lane

Every lane must plan a visual/runtime check:

- open the owned GUI window on Windows, or use Qt offscreen only when real
  Windows visual inspection is unavailable;
- compare visible labels, panels, menus, status bars, warnings and next-action
  text against V38 `GUI_SPEC.yaml`, `WORKSPACE_CONTRACT_MATRIX.csv`,
  `ACCEPTANCE_MATRIX.csv` and `PIPELINE_OPTIMIZED.dot`;
- verify that the user flow follows the optimized graph:
  `SHELL -> PROJECT -> INPUTS -> RING -> SUITE -> BASELINE -> OPT -> ANALYSIS`
  and then `ANALYSIS -> ANIMATOR` or `ANALYSIS -> DIAGNOSTICS`;
- treat tree/search/selection sync as navigation;
- treat mandatory extra click-through buttons as blockers;
- treat service-status dashboards as blockers when they replace operator
  readiness, source, artifact, warning or next-action information;
- keep runtime closure boundaries honest.

Required Plan-mode answer shape:

1. Branch, HEAD, remote and worktree state.
2. Owned files for this lane.
3. Forbidden files for this lane.
4. Relevant V38 requirements and open gaps.
5. Accepted baseline behavior that must be preserved.
6. Visible GUI mismatches.
7. Optimized pipeline mismatches.
8. Minimal implementation plan after approval.
9. Tests and manual Windows checks.
10. Evidence artifacts to update or create.

## 1. Главное Окно И Навигация

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Главное окно и навигация.

Цель:
Довести главное desktop-окно до понятного классического Windows GUI: верхнее меню, дерево маршрута, поиск команд, запуск всех GUI-модулей из одного места, инспектор, status/progress strip и прямой V38 pipeline без лишних кнопок-переходников. WEB не развивать.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
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
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_main_shell_qt_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_main_shell_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_shell_parity_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_home_desktop_gui_launcher_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_web_launcher_desktop_bridge_contract.py`

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo_solver_ui/desktop_mnemo/*`
- optimizer/results internals
- diagnostics producer internals
- model/solver files

Accepted baseline to preserve:
Main shell V38 surfaces, all-launchable-GUI coverage through browser/menu/toolbar/search, direct selection sync, no `desktop_gui_spec_shell` as primary route, no service metadata as primary UI.

Plan must include:
- visible audit of menu/tree/search/inspector/status text;
- check for forbidden labels such as `Статус миграции`, `Открыть выбранный этап`, `Данные машины`;
- pipeline check against `PIPELINE_OPTIMIZED.dot`;
- runtime proof update if behavior changes.

Expected tests after approval:
- `python -m pytest tests/test_desktop_main_shell_qt_contract.py tests/test_desktop_main_shell_contract.py tests/test_desktop_shell_parity_contract.py tests/test_home_desktop_gui_launcher_contract.py tests/test_web_launcher_desktop_bridge_contract.py -q`
```

## 2. Ввод Исходных Данных И Настройки Расчёта

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Ввод исходных данных и настройки расчёта.

Цель:
Довести desktop-окно исходных данных: разделы геометрия, пневматика, механика, компоненты, справочные данные и расчётные настройки; слайдеры и числовые поля; единицы; допустимые диапазоны; источник значения; dirty/current state; снимок исходных данных для следующих этапов.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/02_INPUT_DATA.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_CATALOG.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_VISIBILITY_MATRIX.csv`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_graphics.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_suite_snapshot.py` only for inputs handoff
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_editor_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_graphics_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_suite_snapshot.py`

Forbidden without explicit coordination:
- main shell behavior except adapter registration requests;
- ring editor internals;
- optimizer/results internals;
- model/solver physics files;
- canonical parameter renames not backed by V38 catalog.

Accepted baseline to preserve:
`Исходные данные` label, `Расчётные настройки` display title, source/state markers, snapshot/folder actions and no ad-hoc `Данные машины` wording.

Plan must include:
- visual audit of all input clusters and calculation settings;
- list of missing sliders/ranges/units/source markers;
- direct cluster selection check, without extra "open selected stage" style step;
- handoff check for `inputs_snapshot.json`.

Expected tests after approval:
- `python -m pytest tests/test_desktop_input_editor_contract.py tests/test_desktop_input_graphics_contract.py tests/test_desktop_suite_snapshot.py -q`
```

## 3. Сценарии, Редактор Кольца И Run Setup

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Сценарии, редактор кольца и подготовка прогона.

Цель:
Довести пользовательский сценарный контур: редактор/генератор кольца, сегменты, стыки, проверки, экспорт road/scenario artifacts, подготовка набора испытаний и run setup handoff. Не дублировать input editor и не владеть оптимизатором.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/04_RING_EDITOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_canonical_contract_v13.json`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_run_setup_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/adapters/desktop_ring_editor_adapter.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_ring_editor_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_run_setup_center_contract.py`

Forbidden without explicit coordination:
- `desktop_input_editor.py`;
- optimizer runtime internals;
- results center internals;
- animator/mnemo/compare windows;
- solver/model physics.

Accepted baseline to preserve:
Ring editor remains the primary scenario source. Run setup handoff is integrated. Exported artifacts are derived, not a second editing surface.

Plan must include:
- visual audit of scenario editor and run setup screens;
- V38 path check `INPUTS -> RING -> SUITE -> BASELINE`;
- check that ring selection/export does not require redundant navigation;
- evidence boundary for what is generated versus edited.

Expected tests after approval:
- `python -m pytest tests/test_desktop_ring_editor_contract.py tests/test_desktop_run_setup_center_contract.py -q`
```

## 4. Compare Viewer

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Compare Viewer.

Цель:
Довести Compare Viewer как окно сравнения выбранных прогонов: корректный compare contract, session autoload, objective/influence context, понятные статусы и отсутствие WEB-зависимости. Не дублировать Results Center и Engineering Analysis.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/05_COMPARE_VIEWER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_contract.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_session.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/06_CompareViewer_QT.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_qt_compare_viewer_compare_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_qt_compare_viewer_session_autoload_source.py`

Forbidden without explicit coordination:
- optimizer runtime internals;
- engineering analysis internals;
- desktop animator and mnemo;
- main shell beyond launch registration.

Accepted baseline to preserve:
V38 compare/session behavior is integrated in `codex/work`. Do not create a second compare window or a WEB-first replacement.

Plan must include:
- visible audit of run selection, comparison labels, warnings and export actions;
- proof that compare opens from analysis/results context;
- no service jargon in status bars;
- boundary between Compare Viewer and Engineering Analysis.

Expected tests after approval:
- `python -m pytest tests/test_qt_compare_viewer_compare_contract.py tests/test_qt_compare_viewer_session_autoload_source.py -q`
```

## 5. Desktop Mnemo

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Desktop Mnemo.

Цель:
Довести мнемосхему как отдельное desktop-окно визуализации: корректный запуск, закрытие без зависаний, честные truth-state режимы, нормальные русские подписи и читаемая схема без наложений текста.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/06_DESKTOP_MNEMO.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_MNEMO_WINDOWS_ACCEPTANCE_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_mnemo.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_mnemo_launcher_contract.py`
- mnemo-specific acceptance docs under `docs/context/release_readiness/*MNEMO*`

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- main shell except launch wiring;
- solver/model files.

Accepted baseline to preserve:
Desktop Mnemo is a separate window, not a duplicate animator. Its unavailable/incomplete states must be honest, not hidden.

Plan must include:
- visual audit for clipping, overlap, unreadable labels and mojibake;
- close/reopen behavior check;
- truth-state check against available data;
- explicit statement whether real Windows visual proof is available.

Expected tests after approval:
- `python -m pytest tests/test_desktop_mnemo_launcher_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 6. Desktop Animator

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Desktop Animator.

Цель:
Довести desktop animator как достоверную визуализацию выбранного результата: analysis context, artifact pointers, cylinder render policy, truth modes, capture provenance and clear Russian operator status. Не дублировать Desktop Mnemo и Compare Viewer.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/07_DESKTOP_ANIMATOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_v32_desktop_animator_truth_contract.py`
- animator-specific runtime/evidence docs when needed.

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_mnemo/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- results/optimizer producer internals unless a handoff contract needs a consumer assertion;
- model/solver files.

Accepted baseline to preserve:
`cylinder_render_policy.py` is integrated. Animator status uses operator-facing Russian text for HO-008 context. Do not revert to raw `analysis context/run/context` UI text.

Plan must include:
- visual audit of load state, truth mode labels, cylinder rendering and controls;
- check that animation opens from analysis context, not arbitrary fake data;
- artifact/capture provenance evidence;
- no duplicate mnemo behavior.

Expected tests after approval:
- `python -m pytest tests/test_v32_desktop_animator_truth_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 7. Оптимизатор, Набор Испытаний И Results Center

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Оптимизатор, набор испытаний и центр результатов.

Цель:
Довести контур `SUITE -> BASELINE -> OPT -> ANALYSIS`: набор испытаний, базовый прогон, настройки оптимизации, выбранный прогон, Results Center, resume safety and handoff to Compare/Animator/Diagnostics. Не смешивать управление оптимизацией с визуализацией.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/08_OPTIMIZER_CENTER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_tabs/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_optimizer_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_results_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/autotest_gui.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_optimizer_center_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_test_center_results_center_contract.py`

Forbidden without explicit coordination:
- ring editor generation internals;
- compare viewer internals;
- animator/mnemo internals;
- diagnostics producer internals;
- solver/model physics.

Accepted baseline to preserve:
Optimizer/results workflow handoff is integrated. There must be one active optimization mode, clear selected-run identity and safe resume behavior.

Plan must include:
- visual audit of suite, baseline, optimization settings and results panels;
- V38 pipeline check from suite to analysis;
- check for duplicate launch controls or ambiguous active mode;
- handoff check to Compare Viewer, Animator and Diagnostics.

Expected tests after approval:
- `python -m pytest tests/test_desktop_optimizer_center_contract.py tests/test_test_center_results_center_contract.py -q`
```

## 8. Diagnostics And SEND Bundle

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Диагностика и SEND Bundle.

Цель:
Довести diagnostics center и SEND bundle: health summary, evidence manifest, latest ZIP, validation, inspect/send bundle, honest missing-artifact states and no fake closure.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_diagnostics_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/health_report.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/inspect_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/make_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_bundle_evidence.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/validate_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_diagnostics_center_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_diagnostics_text_encoding_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_health_report_inspect_send_bundle_anim_diagnostics.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_v32_diagnostics_send_bundle_evidence.py`

Forbidden without explicit coordination:
- producer internals in optimizer/results/animator/engineering except consumer evidence reads;
- main shell beyond diagnostics launch/status wiring;
- release packaging outside SEND bundle scope.

Accepted baseline to preserve:
Diagnostics/send bundle honest evidence is integrated. Missing producer artifacts must stay visible as open blockers, not silently marked ready.

Plan must include:
- visual audit of diagnostics center;
- latest bundle and validation flow;
- explicit mapping of missing artifacts to open gaps;
- check for misleading "ready" states.

Expected tests after approval:
- `python -m pytest tests/test_desktop_diagnostics_center_contract.py tests/test_diagnostics_text_encoding_contract.py tests/test_health_report_inspect_send_bundle_anim_diagnostics.py tests/test_v32_diagnostics_send_bundle_evidence.py -q`
```

## 9. Geometry, Catalogs And Reference

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Геометрия, каталоги и справочники.

Цель:
Довести geometry/reference center: каталоги, reference values, producer truth, hardpoints/solver_points gap visibility, validation and clear handoff to input/animator/diagnostics.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/11_GEOMETRY_REFERENCE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_geometry_reference_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/adapters/desktop_geometry_reference_adapter.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_geometry_reference_center_contract.py`

Forbidden without explicit coordination:
- input editor canonical parameter editing;
- animator rendering internals;
- solver/model physics;
- diagnostics producer packaging except evidence reads.

Accepted baseline to preserve:
Geometry/catalogs producer-truth handoff is integrated. Open V38 gap for producer-side hardpoints/solver_points must remain visible until real producer evidence closes it.

Plan must include:
- visual audit of reference center and catalogs;
- explicit open-gap handling for hardpoints/solver_points;
- check that reference data is not silently treated as editable master input;
- handoff/evidence check to diagnostics and animator consumers.

Expected tests after approval:
- `python -m pytest tests/test_desktop_geometry_reference_center_contract.py -q`
```

## 10. Engineering Analysis, Calibration And Influence

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется строго в Plan mode. Ничего не редактируй, не удаляй, не коммить, не пушь и не создавай ветку до принятого плана.

Русское название направления: Инженерный анализ, калибровка и influence.

Цель:
Довести Engineering Analysis center: calibration, influence, selected-run evidence, analysis context, clear charts/tables, handoff to Compare Viewer and Diagnostics. Не подменять Compare Viewer и Results Center.

Сначала выполни Global First-Run Rule и прочитай Global Required Reading, затем:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/12_ENGINEERING_ANALYSIS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/adapters/desktop_engineering_analysis_center_adapter.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_engineering_analysis_center_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_engineering_analysis_contract.py`

Forbidden without explicit coordination:
- Compare Viewer implementation internals;
- optimizer/results producer internals except selected-run contract reads;
- diagnostics packaging internals except evidence handoff;
- solver/model physics.

Accepted baseline to preserve:
Engineering analysis evidence status is integrated and remote branch was removed after merge into `codex/work`. Do not resurrect the old branch.

Plan must include:
- visual audit of analysis/calibration/influence panels;
- evidence status check for selected run and influence outputs;
- boundary check with Compare Viewer and Results Center;
- diagnostics handoff check.

Expected tests after approval:
- `python -m pytest tests/test_desktop_engineering_analysis_center_contract.py tests/test_desktop_engineering_analysis_contract.py -q`
```

## Final Integration Prompt

Use this after individual lanes report their plans or patches.

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Русское название направления: Интеграционная приёмка GUI после V38.

Задача:
Принять результаты параллельных GUI-чатов только после того, как каждый чат указал owned files, forbidden files, V38 visual evidence, optimized pipeline evidence and tests. Не смешивай unrelated changes. Не удаляй ветки или worktree до сверки, что их изменения уже находятся в `codex/work`.

Обязательные проверки:
- `git fetch --all --prune`
- `git status --short --branch`
- `git worktree list --porcelain`
- `git branch -vv --all`
- focused pytest по затронутым lanes
- `python -m pytest tests/test_ui_text_no_mojibake_contract.py -q`
- `git diff --check`

Приёмка допустима только если:
- `codex/work` синхронизирован с `origin/codex/work`;
- нет потерянных dirty-файлов во временных worktree;
- нет служебных UI-формулировок;
- open gaps остаются open, если нет runtime evidence;
- база знаний обновлена через `knowledge_base_sync`;
- итоговый push выполнен в `origin/codex/work`.
```
