# Code-Audit Plan-Mode Start Prompts

Purpose: updated self-contained starter prompts for the same 10 parallel chats,
now informed by the 2026-04-18 code-tree audit.

Use this file for new chats after reading:

- `docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`

This prompt-pack supersedes `14_PLAN_MODE_PARALLEL_START_PROMPTS.md` for new
parallel chat starts because it includes dirty-tree risks and stricter
first-action rules.

## Global First-Run Rule

Every new chat starts in Plan mode.

Plan-mode means:

- inspect only;
- do not edit files;
- do not stage, commit or push;
- do not delete files or worktrees;
- do not run bulk cleanup commands;
- report current branch, dirty files, owned files, forbidden files, proposed
  minimal patch, tests and evidence boundaries;
- wait for user confirmation before implementation.

## 1. Главное Окно И Поверхность Запуска

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Главное окно и поверхность запуска.

Цель:
Стабилизировать классическое Windows GUI главное окно: верхнее меню, единая поверхность запуска всех GUI-модулей, dock/layout поведение, status/progress strip, runtime-proof запуска и нормальная операторская навигация.

Обязательная стартовая проверка:
- выполнить `git status --short --branch`;
- выполнить `git fetch --all --prune`;
- проверить, что работа начинается от `origin/codex/work`, а не от `main`;
- если текущий worktree грязный, не трогать чужие dirty files и не пытаться clean/revert.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/01_MAIN_WINDOW.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`
- `pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/START_PNEUMO_APP.py`
- `pneumo2_R31CN_HF8_repo_root/START_DESKTOP_MAIN_SHELL.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_qt_shell/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell_qt.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/launch_ui.py`
- shell-focused tests, including `tests/test_desktop_main_shell_qt_contract.py` and `tests/test_web_launcher_desktop_bridge_contract.py`

Known dirty-tree risk from audit:
- `START_PNEUMO_APP.py`, `desktop_qt_shell/main_window.py`, `desktop_qt_shell/runtime_proof.py`, `test_desktop_main_shell_qt_contract.py` and `test_web_launcher_desktop_bridge_contract.py` may already be dirty in the primary worktree.
- Your Plan must say whether to adopt, split or leave those changes untouched.

Forbidden without explicit coordination:
- `pneumo_solver_ui/desktop_mnemo/*`
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- optimizer/results, diagnostics/SEND, geometry producer internals

Plan-mode output:
1. Current branch/worktree state.
2. Which shell dirty files exist and what they appear to do.
3. Minimal implementation plan after user approval.
4. Exact owned files to touch.
5. Tests and manual Windows checks.
6. Open evidence boundaries.

Do not implement until the user confirms the plan.
```

## 2. Ввод Исходных Данных

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Ввод исходных данных.

Цель:
Сделать desktop input window понятным: секции геометрия, пневматика, механика и настройки расчёта; слайдеры; единицы; source markers; dirty/current state; frozen snapshot handoff. WEB не расширять.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- работать от `origin/codex/work`;
- если worktree грязный, сначала отразить это в плане.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/02_INPUT_DATA.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_CATALOG.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_VISIBILITY_MATRIX.csv`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_graphics.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_editor_contract.py`

Known dirty-tree risk from audit:
- the owned input files are already dirty in the primary worktree.
- Your Plan must inspect and classify the current dirty diff before proposing new edits.

Forbidden without explicit coordination:
- Mnemo, Animator, Compare Viewer internals;
- optimizer/results runtime;
- producer solver/export truth code;
- shell files except documented launcher metadata requested by shell owner.

Plan-mode output:
1. Current input GUI state and dirty diff summary.
2. Missing user-facing clusters or controls.
3. Minimal patch after approval.
4. Tests and visual checks.
5. Handoff evidence to Ring/Suite/Baseline.

Do not implement until the user confirms the plan.
```

## 3. Desktop Mnemo Windows Acceptance

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Desktop Mnemo Windows Acceptance.

Цель:
Довести Desktop Mnemo до честной Windows acceptance проверки: быстро открывается, не зависает, корректно закрывается, не даёт наложений, сохраняет unavailable/truth states и не выдумывает данные.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- проверить, есть ли dirty Mnemo files в текущем worktree;
- не объявлять visual/runtime closure без durable evidence.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/06_DESKTOP_MNEMO.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/runtime_proof.py`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_mnemo_*`
- Mnemo-specific release evidence notes under `docs/context/release_readiness/`

Known dirty-tree risk from audit:
- `desktop_mnemo/app.py`, `desktop_mnemo/runtime_proof.py`, Mnemo runtime/window tests and `DESKTOP_MNEMO_WINDOWS_ACCEPTANCE_2026-04-18.md` may already be dirty.
- Your Plan must decide whether these changes are complete, partial or unsafe.

Forbidden without explicit coordination:
- `desktop_animator/*` except read-only inspection of `data_bundle.py`;
- `qt_compare_viewer.py`;
- shell files except launcher metadata requested by shell owner;
- producer geometry/export code.

Plan-mode output:
1. Dirty Mnemo diff summary.
2. Startup/no-hang/visual acceptance gap list.
3. Automated vs manual checks.
4. Minimal patch after approval.
5. Exact runtime-proof commands.
6. Pending non-closure statements.

Do not implement until the user confirms the plan.
```

## 4. Compare Viewer

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Compare Viewer.

Цель:
Стабилизировать Compare Viewer как отдельное специализированное окно: session/run load, objective integrity, mismatch banners, current/historical/stale provenance, docks/layout and runtime evidence.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- если используешь prepared worktree `C:\Users\Admin\Documents\GitHub\pneumo2_compare_viewer_acceptance`, сначала проверить его чистоту и актуальность к `origin/codex/work`;
- не править чужие dirty files в primary `codex/work`.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/05_COMPARE_VIEWER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_session.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_qt_compare_*`
- compare runtime/smoke tests

Known audit risk:
- `qt_compare_viewer.py` is a large hotspot file; avoid broad rewrites.
- A clean prepared compare worktree exists, but may need updating before implementation.

Forbidden without explicit coordination:
- optimizer objective producer internals;
- Animator/Mnemo internals;
- diagnostics/SEND bundle files.

Plan-mode output:
1. Compare Viewer branch/worktree state.
2. Current objective/session risks.
3. Minimal patch after approval.
4. Tests and runtime checks.
5. Evidence that remains pending.

Do not implement until the user confirms the plan.
```

## 5. Desktop Animator

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Desktop Animator.

Цель:
Стабилизировать Desktop Animator as truth-preserving visual domain: startup/runtime, frame cadence, truthful geometry states, degraded mode, cylinder/solver-points visibility and no fake geometry.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- если используешь prepared worktree `C:\Users\Admin\Documents\GitHub\pneumo2_desktop_animator_truth_runtime`, проверить чистоту и актуальность;
- не править Mnemo/Compare/Input/Shell dirty files.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/07_DESKTOP_ANIMATOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v12_design_recovery/truthful_graphics_contract_v12.json`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_v32_desktop_animator_truth_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_r*_animator_*.py`

Known audit risk:
- `desktop_animator/app.py` is the largest Python file in the repo; avoid monolithic edits.
- Viewer-layer fabrication is forbidden; producer truth gaps must stay visible.

Forbidden without explicit coordination:
- producer export contracts outside animator-owned adapters;
- Mnemo/Compare/shell dirty files;
- diagnostics warning policy.

Plan-mode output:
1. Animator hotspot and truth gap summary.
2. Producer-owned gaps that must remain visible.
3. Minimal patch after approval.
4. Tests and runtime proof.
5. Manual visual checks.

Do not implement until the user confirms the plan.
```

## 6. Optimizer And Results Center

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Optimizer and Results Center.

Цель:
Сделать desktop optimizer/results workflow понятным: objective contract, baseline policy, run identity, resume safety, selected-run provenance, stale/current banners and result evidence.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- проверить dirty optimizer/results files перед планом;
- не трогать shell/input/Mnemo dirty files.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
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

Known dirty-tree risk from audit:
- `desktop_optimizer_panels.py`, `desktop_optimizer_runtime.py`, `desktop_results_model.py`, `desktop_results_runtime.py`, optimizer/results center tools and their tests are already dirty.
- Your Plan must inspect and classify that diff before proposing changes.

Forbidden without explicit coordination:
- Compare Viewer internals except read-only session contract inspection;
- diagnostics/SEND files;
- Ring editor source-of-truth files.

Plan-mode output:
1. Dirty optimizer/results diff summary.
2. Objective/baseline/run identity risks.
3. Minimal patch after approval.
4. Tests and evidence boundaries.
5. What stays non-runtime-closure.

Do not implement until the user confirms the plan.
```

## 7. Diagnostics And SEND Bundle

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Diagnostics and SEND Bundle.

Цель:
Сделать diagnostics/SEND bundle honest and operator-friendly: evidence manifest, latest pointer, health/self-check, crash/exit triggers, producer-owned warnings and no fake closure.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- если используешь prepared worktree `C:\Users\Admin\Documents\GitHub\pneumo2_diagnostics_send_bundle`, проверить чистоту и актуальность;
- не удалять `send_bundles`, `workspace` или release artifacts без отдельного подтверждения.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
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

Known audit risk:
- ignored artifacts include logs, workspaces and send bundles; blanket cleanup is unsafe.

Forbidden without explicit coordination:
- producer lanes that generate truth artifacts;
- viewer internals except evidence row discovery;
- changing warning-only gaps into passing closure without durable artifacts.

Plan-mode output:
1. Diagnostics/SEND current state.
2. Artifact cleanup safety plan.
3. Evidence manifest gaps.
4. Minimal patch after approval.
5. Tests and generated artifacts.
6. Warnings that remain producer-owned.

Do not implement until the user confirms the plan.
```

## 8. Geometry, Catalogs And Producer Truth

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Geometry, Catalogs and Producer Truth.

Цель:
Закрывать truth-data проблемы на producer/export/reference уровне: solver_points, hardpoints, cylinder packaging passport, road width canonicalization, geometry acceptance and reference catalogs. Viewer-layer fabrication запрещена.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- если используешь prepared worktree `C:\Users\Admin\Documents\GitHub\pneumo2_geometry_producer_truth`, проверить чистоту и актуальность;
- не скрывать producer gaps в viewer code.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
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

Known audit risk:
- solver/model files are large and sensitive; no UI-driven parameter drift.
- `desktop_animator/data_bundle.py` is shared with visual consumers; coordinate before changing.

Forbidden without explicit coordination:
- visual viewer patches in Animator/Mnemo/Compare that hide producer gaps;
- diagnostics warning policy;
- input editor UI unless parameter ownership requires coordinated handoff.

Plan-mode output:
1. Producer truth gap map.
2. Durable evidence candidate list.
3. Minimal patch after approval.
4. Data contract/registry impact.
5. Tests.
6. Viewer lanes that must be notified.

Do not implement until the user confirms the plan.
```

## 9. Engineering Analysis, Calibration And Influence

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Engineering Analysis, Calibration and Influence.

Цель:
Сделать engineering analysis/calibration/influence desktop surfaces traceable: selected-run contract, compare influence, units, report provenance, animator link and diagnostics evidence manifest handoff.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- если используешь prepared worktree `C:\Users\Admin\Documents\GitHub\pneumo2_engineering_analysis_calibration`, проверить чистоту и актуальность;
- не менять optimizer/compare internals без handoff.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/12_ENGINEERING_ANALYSIS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/param_influence_ui.py`
- engineering-analysis/calibration/influence tests

Known audit risk:
- `param_influence_ui.py` is a large file; prefer focused helpers/tests.

Forbidden without explicit coordination:
- optimizer objective producer code;
- Compare Viewer internals except handoff contract inspection;
- Animator rendering internals except context-link metadata.

Plan-mode output:
1. Current analysis/calibration/influence map.
2. Selected-run and report provenance risks.
3. Minimal patch after approval.
4. Handoff points to Animator, Compare and Diagnostics.
5. Tests.
6. Evidence boundaries.

Do not implement until the user confirms the plan.
```

## 10. Ring Editor And Run Setup Handoff

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск этого чата выполняется в Plan mode. Ничего не редактируй, не удаляй, не коммить и не пушь.

Название направления: Ring Editor and Run Setup Handoff.

Цель:
Стабилизировать desktop workflow сценариев колец и настройки расчёта: Ring Editor как единственный source-of-truth, generator/export as derived, suite snapshot handoff, stale/current state and no hidden ring seam closure.

Обязательная стартовая проверка:
- `git status --short --branch`;
- `git fetch --all --prune`;
- если используешь prepared worktree `C:\Users\Admin\Documents\GitHub\pneumo2_ring_run_setup_handoff`, проверить чистоту и актуальность;
- не править input/optimizer dirty files без explicit handoff.

Сначала прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/03_RUN_SETUP.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/04_RING_EDITOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_generator.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_ring_editor_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_run_setup_*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_run_setup_center.py`
- ring/run-setup/suite handoff tests

Known audit risk:
- Ring/run setup is downstream of dirty input changes and upstream of optimizer/results; coordinate handoffs explicitly.

Forbidden without explicit coordination:
- input editor internals except frozen snapshot consumer metadata;
- optimizer internals except suite/baseline handoff contract;
- Animator/Mnemo/Compare viewer internals.

Plan-mode output:
1. Ring/run setup branch/worktree state.
2. Source-of-truth and derived artifact boundaries.
3. Minimal patch after approval.
4. Tests and handoff evidence.
5. Open ring seam questions.

Do not implement until the user confirms the plan.
```
