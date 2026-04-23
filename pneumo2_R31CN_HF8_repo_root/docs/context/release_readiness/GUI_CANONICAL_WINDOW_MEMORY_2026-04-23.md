# GUI canonical window memory — 2026-04-23

## Source archives studied

This note consolidates the current GUI memory from the uploaded report and graph archives:

- `pneumo_chat_consolidated_master_v1 (2).zip`
- `pneumo_codex_tz_spec_connector_reconciled_v38_actualized_with_v10.zip`
- `pneumo_gui_graph_iteration_v15.zip`
- `pneumo_gui_graph_iteration_v16 (1).zip`
- `pneumo_gui_graph_iteration_v17.zip`
- `pneumo_gui_graph_iteration_v18.zip`
- `pneumo_gui_graph_iteration_v19 (1).zip`
- `pneumo_gui_graph_iteration_v20.zip`
- `pneumo_gui_graph_iteration_v21_reconciliation.zip`
- `pneumo_human_gui_report_only_v11_launchpoint_current_vs_canonical.zip`
- `pneumo_human_gui_report_only_v12_window_internal_routes.zip`
- `pneumo_human_gui_report_only_v13_canonical_window_operations.zip`
- `pneumo_human_gui_report_only_v14_tree_dock_context.zip`
- `pneumo_human_gui_report_only_v15_state_continuity_repair_loops (1).zip`
- `pneumo_human_gui_report_only_v16_visibility_priority (1).zip`
- `pneumo_human_gui_report_only_v16_visibility_priority (2).zip`

The raw ZIP files are not repository artifacts. This file is a durable operational memory on top of the already imported GUI knowledge stack.

## Non-negotiable GUI rule

The normal desktop GUI is a main shell with a left tree and real working surfaces. A click in the tree must directly open or focus the relevant dock widget, dock window, or allowed advanced top-level surface. The primary path must not require an intermediate launcher grid, a window center, a second choice button, or service/status pages before the user reaches the editor.

`START_PNEUMO_APP.* -> Запустить GUI` must launch `pneumo_solver_ui.tools.desktop_main_shell_qt` / Desktop Main Shell. `desktop_gui_spec_shell` is not the user-facing primary route; it is only a support/dev contract-check surface.

## Canonical route

The dominant user pipeline is:

`Панель проекта -> Исходные данные -> Сценарии и редактор кольца -> Набор испытаний -> Базовый прогон -> Оптимизация -> Анализ результатов -> Анимация -> Диагностика`.

Required direct tree targets:

- `WS-PROJECT`: `дерево -> Панель проекта`.
- `WS-INPUTS`: `дерево -> Исходные данные`.
- `WS-RING`: `дерево -> Сценарии и редактор кольца`.
- `WS-SUITE`: `дерево -> Набор испытаний`.
- `WS-BASELINE`: `дерево -> Базовый прогон`.
- `WS-OPTIMIZATION`: `дерево -> Оптимизация`.
- `WS-ANALYSIS`: `дерево -> Анализ результатов`.
- `WS-ANIMATOR`: `дерево -> Анимация`.
- `WS-DIAGNOSTICS`: `дерево -> Диагностика`.
- `WIN-COMPARE`: `дерево -> Подробное сравнение` as an advanced Analysis route.
- `WIN-MNEMO`: `дерево -> Мнемосхема` as a specialized visualization route.
- `WS-TOOLS`: `дерево -> Инструменты` as support/advanced tools.

## Surface roles

- `Исходные данные` is the master-copy input editor. It must expose selected parameter group, dirty state, validation state, visual twin, symmetry, two-spring configuration, spring leveling mode/method/residual and graphics truth-state before the user trusts a numeric edit.
- `Сценарии и редактор кольца` is the only editable scenario source-of-truth. The ring editor must dominate the scenario route, show selected segment, turn type, longitudinal end, crossfall, seam state and stale export state.
- `Набор испытаний` consumes scenario source-of-truth. It must not become a second scenario editor. Stale scenario links return to the ring editor.
- `Базовый прогон` owns baseline source selection, run execution, active-baseline policy and handoff to optimization.
- `Оптимизация` has one shell route to `WS-OPTIMIZATION`; home summaries must not compete with it. Objective contract, hard gate, stage rows, underfill/gate reasons and baseline provenance must stay visible.
- `Анализ результатов` owns primary compare. `Compare Viewer` is an advanced route from Analysis, not a competing primary route.
- `Анимация` is a viewport-first workspace/specialized child surface with truth-state, playback, overlays and export capture.
- `Диагностика` is a first-class operational surface. `Собрать диагностику` is the primary action; sending results is secondary and happens after a ready diagnostics bundle.
- `Desktop Mnemo` and `Инструменты` remain available but must not overload the first minutes as equal primary buttons.

## Visibility and state continuity

The first 3-5 seconds in any workspace must answer:

- where the user is in the pipeline;
- which project/context/entity is active;
- whether current state is trusted, dirty, invalid, stale, historical, mismatched or degraded;
- what primary action is safe now;
- where the repair route returns after fixing the problem.

Always-visible shell states:

- active project in top bar;
- current pipeline step in left tree and top/breadcrumb area;
- global `Собрать диагностику` entrypoint;
- cross-workspace warning/message bar when stale/current/historical/truth conflicts exist;
- bottom status/progress strip for current task and diagnostics/send-bundle state.

## Prohibited regressions

- Do not make `desktop_gui_spec_shell` the public `Запустить GUI` target.
- Do not expose service metadata, migration/status jargon or spec/debug shells as the main operator UI.
- Do not add a launcher-grid or center-of-windows as a mandatory step before real editors.
- Do not duplicate scenario editing outside the ring editor.
- Do not split diagnostics into competing `GUI диагностики` and `GUI отправки результатов` entrypoints.
- Do not let Compare Viewer compete with Analysis as the primary compare route.
- Do not hide dirty/stale/mismatch/truth-degraded states inside logs or help text.

## Current implementation implication

The immediate safe target is to keep `desktop_main_shell_qt` as the public GUI launch target and route its tree/search/menu actions to the real existing surfaces while moving each surface toward dock/widget behavior. Existing standalone windows may remain only as explicit fallback/support or advanced second-monitor surfaces until the corresponding dock surface is fully implemented.
