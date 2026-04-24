# GUI duplicate windows audit - 2026-04-23

## Scope

Проверены пользовательские GUI entrypoints, Desktop Main Shell registry и фактические `QMainWindow` / `QDockWidget` / `tk.Tk` поверхности. Цель аудита - найти окна с одинаковой или пересекающейся функцией и сверить их с правилом GUI-spec/knowledge base: один public GUI route, левое дерево открывает рабочий dock/widget/window напрямую, промежуточный launcher-grid и "центр окон" не являются primary path.

Подробная функциональная матрица: [GUI_WINDOW_FUNCTIONALITY_CONTRACT_AUDIT_2026-04-23.md](./GUI_WINDOW_FUNCTIONALITY_CONTRACT_AUDIT_2026-04-23.md).

## Executive Finding

В проекте сейчас есть два слоя для большинства этапов:

- `primary active path`: `START_PNEUMO_APP -> Запустить GUI -> pneumo_solver_ui.tools.desktop_main_shell_qt -> DesktopQtMainShell`, где каждый этап должен жить как dock/widget внутри одного shell.
- `fallback/support path`: старые standalone Tk/Qt окна, которые еще зарегистрированы как fallback-команды, support/dev wrappers или специализированные advanced surfaces.

Это допустимо только как переходное состояние. Блокер для пользователя возникает там, где active path вместо рабочего dock-widget показывает summary/service карточку или предлагает открыть отдельное окно. Такое поведение воспринимается как два интерфейса и дублирование функций. В текущем исправлении левая навигация очищена от service/detail окон: дерево показывает рабочий маршрут и проект, а support/fallback остается в явных меню/toolbar.

## Duplicate Groups

| Функция | Primary по контракту | Дубли / fallback окна | Риск | Решение |
|---|---|---|---|---|
| Запуск приложения | `START_PNEUMO_APP` с явными кнопками `WEB` и `GUI`; GUI ведет в `desktop_main_shell_qt` | `START_DESKTOP_MAIN_SHELL`, `START_DESKTOP_GUI_SPEC_SHELL`, `START_DESKTOP_CONTROL_CENTER`, `desktop_control_center`, legacy `desktop_main_shell` | Несколько оболочек выглядят как разные продукты | Оставить `START_PNEUMO_APP` public launcher. Остальное - support/dev only |
| Главное рабочее окно | `DesktopQtMainShell` | `DesktopGuiSpecMainWindow`, `DesktopControlCenter`, legacy Tk shell | Нарушается правило одного главного shell | `desktop_main_shell_qt` остается единственным public GUI target |
| Исходные данные | Dock `InputWorkspacePage` в `ws_inputs` | Tk `desktop_input_editor`, частично `desktop_geometry_reference_center` | Standalone editor может стать вторым основным редактором | P1 active-route pass: file load/save-as/template restore, search/status/profiles/snapshots/change tracking are hosted; remaining graphics/related-field panes stay fallback until ported |
| Сценарии / редактор кольца | Dock `RingWorkspacePage` в `ws_ring` | Tk `desktop_ring_scenario_editor`, старые web материалы | Самый критичный дубль: сценарий обязан иметь один editable source of truth | P0 active-route исправлен: hosted Ring Editor содержит карточку сегмента, пресеты, события, seam-check и export; Tk editor - fallback only |
| Набор испытаний | Dock `SuiteWorkspacePage` в `ws_suite` плюс фильтр/пресеты, карточка выбранного испытания, автономная проверка, child docks проверки, снимка и autotest | Tk `test_center_gui`, частично `run_autotest_gui` | Test center смешивает suite, results и diagnostics | Suite dock primary; basic autotest runner hosted, results/diagnostics orchestration moves to results/diagnostics |
| Базовый прогон | Dock `BaselineWorkspacePage` в `ws_baseline` плюс child docks политики запуска, предпросмотра дороги, предупреждений, журнала, результатов и передачи в оптимизацию | Tk `desktop_run_setup_center`, backend `desktop_single_run` | Run setup выглядит как второй route запуска, если настройки/предпросмотр/журнал/результаты открываются вне shell | Baseline dock owns run setup, road preview, warning inspection, log/result inspection and optimization handoff; standalone run setup fallback |
| Оптимизация | Dock `OptimizationWorkspacePage` в `ws_optimization` плюс child docks истории, готовых прогонов, передачи стадий и упаковки | Tk `desktop_optimizer_center`, direct wrappers | Теряется один active launch path и provenance baseline | Optimization dock primary; old optimizer remains advanced/fallback until distributed/live-control parity is ported |
| Анализ результатов | Dock `ResultsWorkspacePage` в `ws_analysis` плюс child docks материалов прогона, карточки выбранного материала, подробностей графика, инженерной проверки, кандидатов анализа, фиксации выбранного прогона, запуска расчёта влияния системы, запуска полного отчёта, запуска диапазонов влияния, влияния системы, сравнения влияния, сохранения материалов разбора, связи с анимацией, контекста сравнения, материалов проверки, передачи в анимацию и сравнения результатов с compare-contract/mismatch drilldown, hosted compare-contract summary, hosted compare-session summary, hosted compare plot preview и hosted open-timeline summary | Tk `desktop_results_center`, `desktop_engineering_analysis_center`, Qt `qt_compare_viewer` | Compare/analysis competing first routes | Analysis dock primary; old compare/engineering windows remain advanced/fallback until multi-run plotting/timeline parity is ported |
| Анимация | Dock `AnimationWorkspacePage` в `ws_animator` плюс child docks `child_dock_animation_motion` / `child_dock_animation_mnemo` / `child_dock_animation_diagnostics_handoff` | Qt `desktop_animator.app`, `desktop_mnemo.app` | Специализированные окна должны быть child/floating surfaces, не второй маршрут | First child-dock pass done; standalone Animator/Mnemo remain advanced fallback until rich playback parity |
| Диагностика / отправка | Dock `DiagnosticsWorkspacePage` в `ws_diagnostics` плюс hosted full project check and send review child dock | Tk `desktop_diagnostics_center`, `send_results_gui`, `run_full_diagnostics_gui` | Разделение диагностики и отправки создает две конкурирующие точки | Diagnostics dock primary; full project check, send review and send results inside Diagnostics; legacy fallback |
| Справочники / инструменты | `Tools` / support group inside shell | `desktop_geometry_reference_center`, `run_autotest_gui`, misc tools | Служебщина засоряет первые минуты, если стоит рядом с этапами pipeline | Исправлено для левого дерева: держать в `Инструменты`/toolbar, не показывать как равные этапы |

## Entrypoints Classified

| Entrypoint / class | Toolkit | Current role | Duplicate group | Contract status |
|---|---|---|---|---|
| `START_PNEUMO_APP.py/.cmd` | Tk launcher | Public launcher | App launch | Keep public |
| `pneumo_solver_ui.tools.desktop_main_shell_qt` / `DesktopQtMainShell` | PySide6 | Public GUI shell | Main shell | Keep primary |
| `START_DESKTOP_MAIN_SHELL.py/.cmd` | wrapper | Dev/support shortcut | App launch | Support only |
| `pneumo_solver_ui.tools.desktop_gui_spec_shell` / `DesktopGuiSpecMainWindow` | PySide6 | Spec/dev shell | Main shell | Support/dev only |
| `START_DESKTOP_GUI_SPEC_SHELL.py/.cmd` | wrapper | Spec/dev shortcut | Main shell | Support/dev only |
| `pneumo_solver_ui.tools.desktop_control_center` | Tk | Old window center | Main shell / launcher-grid | Remove from primary route |
| `START_DESKTOP_CONTROL_CENTER.py/.cmd` | wrapper | Old control-center shortcut | Main shell / launcher-grid | Support/debug only |
| `pneumo_solver_ui.tools.desktop_main_shell` | Tk | Legacy fallback shell | Main shell | Fallback only |
| `InputWorkspacePage` | PySide6 widget | Active dock | Input | Primary, P1 active-route pass; graphics/related-field parity remains |
| `pneumo_solver_ui.tools.desktop_input_editor` | Tk | Standalone editor | Input | Fallback until parity |
| `RingWorkspacePage` | PySide6 widget | Active dock | Scenario/ring | Primary, P0 active-route pass; live parity validation remains |
| `pneumo_solver_ui.tools.desktop_ring_scenario_editor` | Tk | Standalone editor | Scenario/ring | Fallback until parity |
| `SuiteWorkspacePage` | PySide6 widget | Active dock with filter/presets, selected-test detail, autonomous check runner and managed child docks for validation/snapshot/autotest review | Test suite | Primary, P1 active-route pass; diagnostics/result orchestration remains |
| `pneumo_solver_ui.tools.test_center_gui` | Tk | Standalone test center | Test suite/results/diagnostics | Fallback/support |
| `BaselineWorkspacePage` | PySide6 widget | Active dock with managed child docks for setup policy, road preview, warnings, log, result files and optimization handoff | Baseline run | Primary, P1 active-route pass; live validation remains |
| `pneumo_solver_ui.tools.desktop_run_setup_center` | Tk | Standalone run setup | Baseline run | Fallback until parity |
| `OptimizationWorkspacePage` | PySide6 widget | Active dock with managed child docks for history, finished runs, stage handoff and packaging | Optimization | Primary, P1 active-route pass; advanced distributed/live-control parity remains |
| `pneumo_solver_ui.tools.desktop_optimizer_center` | Tk | Standalone optimizer | Optimization | Fallback/advanced |
| `ResultsWorkspacePage` | PySide6 widget | Active dock with managed child docks for run materials, selected material, chart detail, engineering QA, analysis candidates, selected-run pinning, non-blocking system-influence launch, non-blocking full-report launch, non-blocking param-staging launch, influence review, compare-influence review, engineering evidence export, animation link, compare context, compare-contract/mismatch review, hosted compare-contract summary, hosted compare-session summary, hosted compare plot preview, hosted open-timeline summary, evidence materials, animation handoff and compare review | Results/analysis | Primary, P1 active-route pass; multi-run plotting/timeline parity remains |
| `pneumo_solver_ui.tools.desktop_results_center` | Tk | Standalone results center | Results/analysis | Fallback/support |
| `pneumo_solver_ui.tools.desktop_engineering_analysis_center` | Tk | Detailed analysis fallback | Results/analysis | Advanced/support after hosted engineering check |
| `pneumo_solver_ui.qt_compare_viewer.CompareViewer` | PySide6 | Detailed compare | Results/analysis | Advanced child/specialized |
| `AnimationWorkspacePage` | PySide6 widget | Active dock/hub with managed child dock checks and diagnostics handoff | Animation | Primary, first child-dock pass; playback parity incomplete |
| `pneumo_solver_ui.desktop_animator.app.MainWindow` | PySide6 | Specialized visual window | Animation | Advanced fallback until hosted playback parity |
| `pneumo_solver_ui.desktop_mnemo.app.MnemoMainWindow` | PySide6 | Specialized mnemo window | Animation/results | Advanced fallback until hosted mnemo parity |
| `DiagnosticsWorkspacePage` | PySide6 widget | Active dock with full project check, send review and bundle/send actions | Diagnostics/send | Primary, strongest compliance |
| `pneumo_solver_ui.tools.desktop_diagnostics_center` | Tk | Standalone diagnostics | Diagnostics/send | Fallback only |
| `pneumo_solver_ui.tools.send_results_gui` | Tk | Standalone send bundle | Diagnostics/send | Secondary action only |
| `pneumo_solver_ui.tools.run_full_diagnostics_gui` | Tk | Standalone full diagnostics | Diagnostics/send | Support/fallback |
| `pneumo_solver_ui.tools.desktop_geometry_reference_center` | Tk | Reference/support | Input/reference | Support only |
| `pneumo_solver_ui.tools.run_autotest_gui` | Tk | Autotest/support | Suite/diagnostics | Support only |

## Immediate Corrections Already Made

1. Route-critical dock surfaces are no longer initialized as summary-only service cards. `DesktopQtMainShell._build_workspace_child_docks()` installs hosted pages immediately when a hosted workspace exists: inputs, ring, suite, baseline, optimization, analysis, animation and diagnostics.
2. Saved binary Qt geometry/window state is no longer restored on startup by default. Semantic state is still restored, but `restoreGeometry()` / `restoreState()` now require explicit `PNEUMO_QT_MAIN_SHELL_RESTORE_BINARY_LAYOUT=1` or the menu action. This mitigates the observed native crash when moving the window after layout changes.
3. Operator-visible audit now ignores hidden route pages, so hidden service/path text does not pollute visible-window checks.
4. Left tree no longer exposes service/detail/fallback windows as primary route items. Tree selection is now route-first; support remains explicit in menu/toolbar.
5. `RingWorkspacePage` is no longer a thin table. It now includes ring/segment presets, selected-segment detail fields, road/crossfall controls, segment events, source/stale status and artifact export from the hosted dock.
6. `InputWorkspacePage` now hosts file load, save-as, template restore, field search, section readiness/issues, route snapshot state, quick presets, profile save/load, snapshot save/load and changed-field tracking in the main dock.
7. `AnimationWorkspacePage` commands now return managed child dock payloads that `DesktopQtMainShell` opens as real dock panels for motion, mnemo and diagnostics handoff checks. The shell also synchronizes `PNEUMO_WORKSPACE_DIR` / `PNEUMO_PROJECT` with the active project context so hosted runtime reads the same workspace as the launcher.
8. `BaselineWorkspacePage` now shows setup policy, road preview, warnings, baseline log, result files and baseline-to-optimization handoff as managed child dock panels inside `DesktopQtMainShell`; these active commands no longer open standalone file/window routes.
9. `OptimizationWorkspacePage` now shows launch history, finished runs, stage handoff candidates and packaging/release state as managed child dock panels inside `DesktopQtMainShell`; the old optimizer center is no longer needed for these first-review surfaces.
10. `ResultsWorkspacePage` now shows compare context, evidence materials, animation handoff and compare review as managed child dock panels inside `DesktopQtMainShell`; the old results/compare windows are no longer needed for these first-review surfaces.
11. `SuiteWorkspacePage` now shows filter/preset controls, selected-test detail, validation review, snapshot review and autonomous check launch/log review inside the hosted route; the old test center is no longer needed for basic suite inspection or basic autotest launch.
12. `DiagnosticsWorkspacePage` now exposes full project check as a hosted button and command-search route, so the old test center is no longer needed for launching `run_full_diagnostics.py`.
13. `DiagnosticsWorkspacePage` now shows send-material review as a managed child dock, so the old test center/send window is no longer needed for the handoff summary.
14. `ResultsWorkspacePage` now shows latest run materials as a managed child dock, so the old test center results tab is no longer needed for the run handoff summary.
15. `ResultsWorkspacePage` now shows engineering QA readiness, selected-run contract state, missing inputs and candidate readiness as a managed child dock, so the old engineering analysis window is no longer required for first-pass analysis readiness.
16. `ResultsWorkspacePage` now shows system-influence materials, sensitivity rows, pipeline rows, chart/table previews and required artifact gaps as a managed child dock, so the old engineering analysis window is no longer required for first-pass influence review.
17. `ResultsWorkspacePage` now shows compare-influence readiness, result sources and top parameter/metric links as a managed child dock, so the old engineering analysis window is no longer required for first-pass influence comparison.
18. `ResultsWorkspacePage` now saves engineering analysis evidence manifest as a managed child dock action, so the old engineering analysis window is no longer required just to prepare diagnostics materials.
19. `ResultsWorkspacePage` now prepares the analysis-to-animation link as a managed child dock action, so the old engineering analysis window is no longer required just to connect the selected result to animation.
20. `ResultsWorkspacePage` now shows optimization run candidates for engineering analysis as a managed child dock, so the old engineering analysis window is no longer required just to inspect ready/problem candidates.
21. `ResultsWorkspacePage` now fixes a ready optimization run as the selected engineering-analysis source in a managed child dock and auto-saves diagnostics evidence when possible, so the old engineering analysis window is no longer required just to accept a candidate run.
22. `ResultsWorkspacePage` now starts the system-influence calculation through a non-blocking Qt process and reports the command/log in a managed child dock, so the old engineering analysis window is no longer required just to run the first influence calculation.
23. `ResultsWorkspacePage` now starts the full-report calculation through the same non-blocking Qt job path and shows the command/log in a managed child dock, so the old engineering analysis window is no longer required just to build the first full report.
24. `ResultsWorkspacePage` now starts the parameter-staging calculation (`Диапазоны влияния`) through the same non-blocking Qt job path and shows the command/log in a managed child dock, so the old engineering analysis window is no longer required just to build the first staging ranges.
25. `ResultsWorkspacePage` now shows the selected result artifact as a managed child dock with compare target, animation targets and preview lines, so the old results/engineering windows are no longer required just to inspect the chosen material card.
26. `ResultsWorkspacePage` now shows the selected chart series as a managed child dock with range, sample points and compare-context, so the old compare viewer is no longer required just to inspect the first numeric drilldown.
27. `ResultsWorkspacePage` now shows compare-contract state, selected/current context fields, mismatch rows and selected-run contract markers inside the compare child dock, so the old compare viewer is no longer required for the first contract-level compare review.
28. `ResultsWorkspacePage` now builds a hosted compare-contract summary from the same runtime/contract layer as the compare stack and shows table, signals, time window, alignment, source and mismatch banner inside the compare child dock, so the old compare viewer is no longer required for the first compare-session summary.
29. `ResultsWorkspacePage` now builds a hosted compare-session summary with run refs, table/signals, time window and playhead context inside the compare child dock, so the old compare viewer is no longer required for the first multi-run/session review.
30. `ResultsWorkspacePage` now builds a hosted open-timeline summary from the selected `open` table and shows valve counts, changed valves, time window and top changing valves inside the compare child dock, so the old compare viewer is no longer required for the first valve-timeline review.
31. `ResultsWorkspacePage` now builds a hosted pairwise peak-delta hotspot summary from the selected result and the current latest NPZ, so the old compare viewer is no longer required for the first heat-style hotspot review.
32. `ResultsWorkspacePage` now builds a hosted pairwise delta-timeline preview for the selected/prioritized signal and shows reference/current values around the hotspot, so the old compare viewer is no longer required for the first time-local `Δ(t)` slice review.

33. `ResultsWorkspacePage` now adds a hosted peak-competition bridge summary with dominant signal/run and the recommended handoff into Delta timeline, so the old compare viewer is no longer required for the first hotspot-to-timeline routing decision.
34. `ResultsWorkspacePage` now shows a hosted compare-session roster with pair label, target signal, target window and per-run roles/sources, so the old compare viewer is no longer required for the first multi-run routing review before opening full timeline tooling.
35. `ResultsWorkspacePage` now exposes hosted compare target/signal switch controls that cycle the active artifact and numeric series inside the main shell and immediately refresh the compare child dock, so the old compare viewer is no longer required for the first pair/signal retargeting step.
36. `ResultsWorkspacePage` now exposes a hosted compare playhead switch that cycles the active `Δ(t)` point inside the main shell and immediately refreshes the compare child dock with the selected time/ref/compare/delta values, so the old compare viewer is no longer required for the first timeline-point drilldown.
37. `ResultsWorkspacePage` now exposes a hosted compare time-window switch that cycles the active time scope inside the main shell and immediately refreshes the compare child dock with the selected window bounds and point count, so the old compare viewer is no longer required for the first window-of-interest drilldown.
38. `ResultsWorkspacePage` now renders the first hosted compare plot preview directly inside the compare child dock, with reference/current/Δ lines plus active window/playhead focus, so the old compare viewer is no longer required for the first plot-level drilldown.

## Remaining Gaps

- Primary dock pages exist, but several still lack full feature parity with old Tk/Qt windows. Fallback windows must remain until each stage reaches parity, but they must not be exposed as equal first-choice routes.
- The biggest remaining parity gaps are input graphics/related-field panes, live validation of hosted baseline preview/warnings, advanced distributed optimization controls, rich animation playback/overlay parity, full multi-run compare heatmap/timeline tooling beyond the first hosted plot drilldown and live validation that the hosted `RingWorkspacePage` covers all legacy details.
- `desktop_gui_spec_shell`, `desktop_control_center` and wrapper shortcuts must stay out of normal user launch flow to avoid the "two interfaces" failure mode.
