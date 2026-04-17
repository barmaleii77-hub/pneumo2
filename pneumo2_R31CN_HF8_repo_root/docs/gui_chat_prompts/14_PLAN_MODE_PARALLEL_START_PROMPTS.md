# Plan-Mode Parallel Start Prompts

Purpose: copy-paste starter prompts for new parallel Codex chats after the
2026-04-18 branch cleanup. Each prompt assumes the first launch of the chat is
in Plan mode.

Use these prompts to keep parallel work useful without recreating branch chaos.
Do not start every lane at once. Keep 3-5 active implementation chats at most,
and only when their owned files do not overlap.

## Common Rules For Every New Chat

- Start from `origin/codex/work`, not from `main`.
- In Plan mode, do not edit files, do not create commits and do not push.
- First produce a short plan with scope, owned files, forbidden files, tests,
  risks and at most three blocking questions.
- After the plan is accepted, implementation should happen on a new branch from
  `codex/work`, using the `codex/` prefix.
- Do not expand WEB. WEB is only legacy reference while operator flows migrate
  to classic Windows desktop GUI.
- Do not duplicate `Desktop Animator`, `Compare Viewer` or `Desktop Mnemo`
  internals in other windows.
- Capture every new user requirement or generated plan in the knowledge-base
  layer.
- Keep release evidence honest: do not claim runtime closure without durable
  artifacts and focused tests.

## 1. Главное Окно И Поверхность Запуска

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Главное окно и поверхность запуска.

Цель:
Стабилизировать классическое Windows GUI главное окно: верхнее меню, единое место запуска всех GUI-модулей, docks, статусную строку, runtime-proof запуска и понятную операторскую навигацию.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед любым планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/main-shell-launch-surface`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/PROJECT_SOURCES.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/01_MAIN_WINDOW.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_qt_shell/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell_qt.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/launch_ui.py`
- `pneumo2_R31CN_HF8_repo_root/START_DESKTOP_MAIN_SHELL.py`
- `pneumo2_R31CN_HF8_repo_root/START_PNEUMO_APP.py`
- shell-focused tests only

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_mnemo/*`
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- optimizer, diagnostics, geometry producer internals

Plan-mode output:
1. Сводка текущего состояния shell и рисков.
2. Предлагаемый минимальный следующий patch.
3. Точный список файлов, которые будут изменены.
4. Тесты и manual runtime checks.
5. Что останется pending.
6. До трёх вопросов, только если без ответа нельзя безопасно продолжать.

Ничего не меняй до подтверждения плана пользователем.
```

## 2. Ввод Исходных Данных

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Ввод исходных данных.

Цель:
Сделать desktop-окно ввода исходных данных понятным пользователю: секции геометрия, пневматика, механика, расчётные настройки, слайдеры, единицы, source markers, dirty/current state и frozen snapshot handoff.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/input-data-gui`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/PROJECT_SOURCES.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/02_INPUT_DATA.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_CATALOG.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_VISIBILITY_MATRIX.csv`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_graphics.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_editor_contract.py`

Forbidden without explicit coordination:
- shell launch internals except adding documented command metadata requested by shell owner;
- `desktop_mnemo`, `desktop_animator`, `qt_compare_viewer`;
- solver/export truth code.

Plan-mode output:
1. Карта текущих input controls и недостающих пользовательских секций.
2. Минимальный patch, который улучшает понятность без WEB-расширения.
3. Owned file list and non-owned boundaries.
4. Contract tests and visual/manual checks.
5. Handoff evidence to Ring/Suite/Baseline.

Ничего не меняй до подтверждения плана пользователем.
```

## 3. Desktop Mnemo Windows Acceptance

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Desktop Mnemo Windows Acceptance.

Цель:
Закрыть ближайший пользовательский риск по Desktop Mnemo: окно должно открываться быстро, не зависать, корректно закрываться, не давать визуальных наложений и не скрывать unavailable/truth states. Не выдумывать данные и не рисовать fake truth.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/desktop-mnemo-windows-acceptance`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/06_DESKTOP_MNEMO.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/runtime_proof.py`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_mnemo_*`
- Mnemo-specific release evidence notes under `docs/context/release_readiness/`

Forbidden without explicit coordination:
- `desktop_animator/*` except read-only inspection of `data_bundle.py`;
- `qt_compare_viewer.py`;
- main shell files except launcher metadata requested by shell owner;
- producer geometry/export code.

Plan-mode output:
1. Startup and visual acceptance gap list.
2. What can be automated vs what must remain manual.
3. Minimal patch proposal.
4. Exact runtime-proof commands to run.
5. Focused tests.
6. Explicit non-closure statements that must remain pending.

Ничего не меняй до подтверждения плана пользователем.
```

## 4. Compare Viewer

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Compare Viewer.

Цель:
Стабилизировать Compare Viewer как отдельное специализированное окно: загрузка run/session, objective integrity, mismatch banners, current/historical/stale provenance, docks/layout и runtime evidence без дублирования optimizer или animator internals.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/compare-viewer-acceptance`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/05_COMPARE_VIEWER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_session.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_qt_compare_*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_r64_qt_compare_*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_r65_qt_compare_*`

Forbidden without explicit coordination:
- optimizer objective producer internals;
- `desktop_animator/*`;
- `desktop_mnemo/*`;
- diagnostics/SEND bundle files.

Plan-mode output:
1. Compare Viewer current gap map.
2. Objective/session provenance risks.
3. Minimal patch proposal.
4. Owned files and boundaries.
5. Tests and runtime/manual checks.
6. Evidence that must stay pending if not durable.

Ничего не меняй до подтверждения плана пользователем.
```

## 5. Desktop Animator

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Desktop Animator.

Цель:
Стабилизировать Desktop Animator как отдельный truth-preserving visual domain: startup/runtime, frame cadence, truthful geometry states, degraded mode, cylinder/solver-points visibility and no fake geometry.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/desktop-animator-truth-runtime`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/07_DESKTOP_ANIMATOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v12_design_recovery/truthful_graphics_contract_v12.json`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_v32_desktop_animator_truth_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_r*_animator_*.py`

Forbidden without explicit coordination:
- producer export contracts outside animator-owned adapters;
- `desktop_mnemo/*`;
- `qt_compare_viewer.py`;
- main shell files except launcher metadata requested by shell owner.

Plan-mode output:
1. Animator truth/runtime risk summary.
2. Which gaps are producer-owned and must not be hidden in viewer code.
3. Minimal patch proposal.
4. Tests and runtime proof commands.
5. Manual visual checks.
6. Explicit open gaps.

Ничего не меняй до подтверждения плана пользователем.
```

## 6. Optimizer And Results Center

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Optimizer and Results Center.

Цель:
Перенести optimizer/results operator workflow в понятный desktop GUI: objective contract, baseline policy, run identity, resume safety, selected-run provenance, stale/current banners and result evidence.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/optimizer-results-center`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/08_OPTIMIZER_CENTER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v12_design_recovery/optimization_control_plane_contract_v12.json`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_tabs/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_optimizer_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_results_center.py`
- optimizer/results-focused tests

Forbidden without explicit coordination:
- Compare Viewer internals except read-only session contract inspection;
- diagnostics/SEND files;
- Ring editor source-of-truth files unless handoff owner agrees.

Plan-mode output:
1. Current optimizer/results workflow map.
2. Objective/baseline/run identity risks.
3. Minimal patch proposal.
4. File ownership and boundaries.
5. Tests.
6. What remains non-runtime-closure.

Ничего не меняй до подтверждения плана пользователем.
```

## 7. Diagnostics And SEND Bundle

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Diagnostics and SEND Bundle.

Цель:
Сделать diagnostics/SEND bundle honest and operator-friendly: evidence manifest, latest pointer, health/self-check, crash/exit triggers, producer-owned warnings and no fake closure.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/diagnostics-send-bundle`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/make_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/validate_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_bundle_evidence.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/health_report.py`
- diagnostics/SEND-focused tests

Forbidden without explicit coordination:
- producer lanes that generate truth artifacts;
- viewer internals except evidence row discovery;
- changing warning-only gaps into passing closure without durable artifacts.

Plan-mode output:
1. Diagnostics/SEND current status.
2. Evidence manifest gaps.
3. Minimal patch proposal.
4. Tests and generated artifacts.
5. Which warnings remain producer-owned.
6. Release-closure language to avoid.

Ничего не меняй до подтверждения плана пользователем.
```

## 8. Geometry, Catalogs And Producer Truth

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Geometry, Catalogs and Producer Truth.

Цель:
Закрывать truth-data проблемы на producer/export/reference уровне: solver_points, hardpoints, cylinder packaging passport, road width canonicalization, geometry acceptance and reference catalogs. Viewer-layer fabrication запрещена.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/geometry-producer-truth`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/11_GEOMETRY_REFERENCE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/01_PARAMETER_REGISTRY.md`
- `pneumo2_R31CN_HF8_repo_root/DATA_CONTRACT_UNIFIED_KEYS.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/anim_export_contract.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/anim_export_meta.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_geometry_reference_center.py`
- geometry/producer truth tests

Forbidden without explicit coordination:
- visual viewer patches in Animator/Mnemo/Compare that hide producer gaps;
- diagnostics warning policy;
- input editor UI unless parameter ownership requires coordinated handoff.

Plan-mode output:
1. Producer truth gap map.
2. Which evidence can be made durable now.
3. Minimal patch proposal.
4. Data contract/registry impact.
5. Tests.
6. Viewer lanes that must be notified.

Ничего не меняй до подтверждения плана пользователем.
```

## 9. Engineering Analysis, Calibration And Influence

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Engineering Analysis, Calibration and Influence.

Цель:
Сделать engineering analysis/calibration/influence desktop surfaces понятными и traceable: selected-run contract, compare influence, units, report provenance, animator link and diagnostics evidence manifest handoff.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/engineering-analysis-calibration`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/12_ENGINEERING_ANALYSIS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/param_influence_ui.py`
- engineering-analysis/calibration/influence tests

Forbidden without explicit coordination:
- optimizer objective producer code;
- Compare Viewer internals except handoff contract inspection;
- Animator rendering internals except context-link metadata.

Plan-mode output:
1. Current analysis/calibration/influence map.
2. Selected-run and report provenance risks.
3. Minimal patch proposal.
4. Handoff points to Animator, Compare and Diagnostics.
5. Tests.
6. Evidence boundaries.

Ничего не меняй до подтверждения плана пользователем.
```

## 10. Ring Editor And Run Setup Handoff

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. На этом этапе ничего не редактируй, не коммить и не пушь.

Название направления: Ring Editor and Run Setup Handoff.

Цель:
Стабилизировать desktop workflow сценариев колец и настройки расчёта: Ring Editor как единственный source-of-truth, generator/export as derived, suite snapshot handoff, stale/current state and no hidden ring seam closure.

Стартовая база:
- работать только от актуальной ветки `codex/work`;
- перед планом проверить `git status --short --branch` и `git fetch --all --prune`;
- после утверждения плана создать отдельную ветку от `origin/codex/work`, например `codex/ring-run-setup-handoff`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/03_RUN_SETUP.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/04_RING_EDITOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_generator.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_run_setup_center.py`
- ring/run-setup/suite handoff tests

Forbidden without explicit coordination:
- input editor internals except frozen snapshot consumer metadata;
- optimizer internals except suite/baseline handoff contract;
- Animator/Mnemo/Compare viewer internals.

Plan-mode output:
1. Ring/run setup current workflow map.
2. Source-of-truth and derived artifact boundaries.
3. Minimal patch proposal.
4. Tests and handoff evidence.
5. Open ring seam questions.

Ничего не меняй до подтверждения плана пользователем.
```
