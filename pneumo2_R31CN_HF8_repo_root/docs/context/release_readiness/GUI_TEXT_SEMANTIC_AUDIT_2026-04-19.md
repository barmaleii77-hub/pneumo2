# GUI text semantic audit 2026-04-19

## Scope

Audit target: current desktop GUI code and V38 GUI/TZ/spec layer.

Sources checked:

- `docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md`
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml`
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv`
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/UI_ELEMENT_CATALOG.csv`
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/WINDOW_CATALOG.csv`
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/PIPELINE_OPTIMIZED.dot`
- desktop GUI sources under `pneumo_solver_ui/desktop_*`, `pneumo_solver_ui/desktop_*/*`, `pneumo_solver_ui/tools/desktop_*`, GUI helper tools, `pneumo_solver_ui/qt_compare_viewer.py`

Static extraction result:

- Desktop GUI files scanned: 119.
- Visible or near-visible GUI strings captured: 2087.
- Exact matches with V38 workspace/window/UI names: 74.
- High-confidence semantic/text issues: 106.
- Refined mojibake detector did not find high-confidence visible mojibake in the scanned desktop GUI strings.

## Normalized User Pipeline

The intended user flow is:

1. Панель проекта
2. Исходные данные
3. Редактор циклического сценария
4. Набор испытаний / матрица испытаний
5. Базовый прогон
6. Оптимизация
7. Анализ результатов
8. Аниматор / Desktop Mnemo / Compare Viewer as explicit consumers of analysis context
9. Диагностика / SEND package

Support surfaces:

- Параметры приложения
- Инструменты
- Справочники
- Автотесты
- Maintenance and recovery commands

Support surfaces must not look like required steps in the main engineering route.

## V38 Semantic Ambiguities

V38 is directionally aligned with the user pipeline, but it is not fully unambiguous.

- `WS-RING` is named `Редактор циклического сценария` in `WORKSPACE_CONTRACT_MATRIX.csv`, while `GUI_SPEC.yaml` and screen catalogs use `Редактор кольца`. Recommended canonical user-facing name: `Редактор циклического сценария`; `Редактор кольца` may remain a short alias.
- `WS-SUITE` is named `Набор испытаний` in `WORKSPACE_CONTRACT_MATRIX.csv`, while `GUI_SPEC.yaml` and screen catalogs frequently say `Матрица испытаний`. Recommended canonical user-facing name: `Набор испытаний`; `Матрица испытаний` is the table/screen inside that workspace.
- `PIPELINE_OPTIMIZED.dot` includes `WS-SHELL`, but the user pipeline starts at `WS-PROJECT`. This is not a conflict if shell is treated as the container, not as a user step.
- V38 contains English technical labels such as `source-of-truth`, `handoff`, `workspace`, `runtime`, `contract`, `manifest`, `provenance`, `bundle`. These are acceptable in internal artifacts only. They must not leak into operator-facing labels, buttons, status lines, dialogs, or help summaries.

## Pipeline And Meaning Check

The graph and V38 logic agree on the core handoff chain:

- `WS-INPUTS` owns editable model inputs.
- `WS-RING` owns editable scenario/road geometry.
- `WS-SUITE` consumes ring exports and does not own scenario geometry.
- `WS-BASELINE` consumes validated suite snapshot.
- `WS-OPTIMIZATION` consumes active baseline and objective contract.
- `WS-ANALYSIS` consumes selected frozen run.
- `WS-ANIMATOR`, `Desktop Mnemo`, and `Compare Viewer` consume explicit analysis/result context.
- `WS-DIAGNOSTICS` collects evidence and SEND package from explicit manifests and current project state.

The current code partially follows this graph, but user-facing text still mixes route logic with implementation logic.

## High-Confidence Violations

### Main shell and registry

Files:

- `pneumo_solver_ui/desktop_spec_shell/registry.py`
- `pneumo_solver_ui/desktop_spec_shell/workspace_pages.py`
- `pneumo_solver_ui/desktop_spec_shell/main_window.py`
- `pneumo_solver_ui/desktop_shell/launcher_catalog.py`

Problems:

- User-visible command titles contain `workspace`, for example `Открыть workspace "Исходные данные"`.
- User-visible descriptions contain internal words: `master-copy`, `hosted workspace`, `legacy editor`, `fallback surface`, `derived artifacts`, `launch contract`, `runtime monitor`, `source-of-truth`, `provenance`.
- `Контракт workspace` appears as a visible group title.
- `Контекст и provenance` and `Свойства, помощь и provenance` are visible labels.
- `Резервное`, `прежнее`, `legacy`, `Tk` surfaces are still too prominent and look like product features, not recovery tools.

Required semantic correction:

- Replace `workspace` in user-facing text with `раздел`, `рабочая область`, or the concrete domain name.
- Replace `contract` with `условия`, `настройки`, `проверенная связка`, or `принятый результат`, depending on context.
- Replace `provenance` with `происхождение данных`.
- Move old/recovery launchers into support/recovery wording and hide them from the main route.

### Project panel

Current code still uses `Обзор` as the main project surface in some places.

V38 canonical meaning is `Панель проекта`: project health, blockers, recent activity, and next action.

Required semantic correction:

- Use `Панель проекта` for the workspace.
- `Обзор` may be a screen/tab inside the panel, not the pipeline node name.

### Inputs

Core placement is mostly correct: `Исходные данные` owns model input editing.

Problems:

- Some summaries still say `master-copy`, `workspace`, `legacy editor`, `baseline`, `optimization`.
- Search aliases may include useful technical aliases, but primary visible descriptions must be Russian and user-domain oriented.

Required semantic correction:

- Primary visible text: geometry, pneumatics, mechanics, calculation settings, checks, ranges, saved input snapshot.
- Keep cache/folder actions only where the user understands what folder is being opened; avoid placing cache wording inside engineering input flow unless it is clearly a file-management tool.

### Ring/scenario editor

Core placement is correct: it is the only editable scenario/road source.

Problems:

- `Сценарии и редактор кольца` can imply a geometric ring, while V38 forbids drawing scenario as a geometric loop.
- Some text still says `derived artifacts`, `single source of truth`, `ring editor` in mixed English/Russian.

Required semantic correction:

- Prefer `Редактор циклического сценария`.
- Use `Редактор кольца` only as a short alias in search/help.
- User text must say what is edited: segments, road profile, seam/check, export to tests.

### Test suite / validation / results

Core placement is partially correct, but naming is inconsistent.

Problems:

- `Набор испытаний` and `Матрица испытаний` are mixed as if they are the same level.
- Some text uses `stage`, `snapshot`, `validation`, `timeline` as primary user wording.

Required semantic correction:

- Workspace: `Набор испытаний`.
- Screen/table: `Матрица испытаний`.
- `validated snapshot` should become `проверенный снимок набора`.
- `stage` should become `этап` only where it describes test rows, not main GUI navigation.

### Baseline

Core placement is correct: baseline follows suite and precedes optimization.

Problems:

- `baseline` leaks in mixed-language summaries and route labels.
- `Контракт запуска` wording is too implementation-oriented.

Required semantic correction:

- Primary label: `Базовый прогон` or `Опорный прогон`.
- Explain user task: create, inspect, accept, restore, pass to optimization.

### Optimization

Core placement is correct: optimization consumes baseline and objective settings.

Problems:

- Visible texts include `Launch contract`, `objective stack`, `hard gates`, `runtime monitor`, `StageRunner`, `distributed coordinator`, `handoff`, `pipeline/backend`.
- Dialog titles still show `Desktop Optimizer Center`.
- Some buttons say `Сделать текущим указателем`, which describes implementation, not user intent.

Required semantic correction:

- `Сделать текущим указателем` -> `Выбрать этот прогон для анализа`.
- `Desktop Optimizer Center` -> `Центр оптимизации`.
- `runtime progress` -> `ход выполнения`.
- `handoff` -> `передать в анализ`.
- `objective stack` -> `цели расчёта`.

### Analysis and Compare Viewer

Core placement is correct: analysis consumes selected frozen run; Compare Viewer is a specialized analysis window.

Problems:

- `qt_compare_viewer.py` still exposes English UI strings such as `Compare contract`, `Compare overview`, `Load compare bundle`, and English tooltips.
- `Geometry acceptance checks the frame / wheel / road solver-point contract...` is visible English/service wording.

Required semantic correction:

- Keep `Compare Viewer` as a proper module name if desired, but translate actual dock titles and tooltips.
- `Compare contract` -> `Условия сравнения`.
- `Load compare bundle` -> `Загрузить набор для сравнения`.
- `Geometry acceptance...` -> Russian explanation of frame/wheel/road geometry checks.

### Animator, Desktop Mnemo, Compare

These are not forbidden zones. They are specialized windows that may be changed carefully.

Semantic rule:

- Do not duplicate their domain responsibility in other workspaces.
- Do not break working behavior.
- They must consume explicit analysis/result context.
- They must expose truthful graphics state and units.

Problems found:

- Desktop Mnemo still contains visible English summaries such as `Unavailable Desktop Mnemo surfaces`.
- Some status/tooltip text still uses `NPZ bundle`, `canonical`, `latched`, or English state names.
- Animator source-level contract tests are currently out of sync with Russian visible UI; proof markers must be internal, not English user labels.

Required semantic correction:

- Keep proper names `Desktop Mnemo` and `Desktop Animator` if the product uses them.
- Translate status messages and warnings around missing data, approximate surfaces, pressure/state availability, and reloads.

### Diagnostics / SEND

Core placement is correct: diagnostics is first-class and always reachable.

Problems:

- Visible labels include `bundle`, `legacy center`, `workspace`, `diagnostics artifacts`.
- Previous user feedback identifies a deeper UX issue: long operations must show progress on the same tab/surface where they start.

Required semantic correction:

- `bundle` -> `архив диагностики` or `пакет диагностики SEND`.
- `Проверить bundle` -> `Проверить архив диагностики`.
- `Открыть legacy center` -> recovery/support wording only, not primary action.
- Any long process launched in diagnostics must show progress in the same visible section and must not draw progress on another tab.

### Settings and Tools

Core placement is correct only if these are support surfaces.

Problems:

- Current text can make `Tools workspace`, `Geometry Reference Center`, `Autotest GUI`, `Engineering Analysis Center` look like mixed product areas rather than support/engineering tools.

Required semantic correction:

- Primary visible names should be Russian:
  - `Справочник геометрии`
  - `Инженерный анализ`
  - `Автопроверка`
  - `Параметры приложения`
- English names may stay in search aliases or developer docs.

## Explicit False Positives

- `Статус миграции`, `Открыть выбранный этап`, and `Данные машины` are present in `pneumo_solver_ui/desktop_qt_shell/pipeline_surfaces.py` only as forbidden-label guards. That is not a visible UI violation.
- The refined scan found no high-confidence visible `Папка кэша` string in desktop GUI code.

## Required Normalization Vocabulary

Use in user-facing GUI:

- `Панель проекта`
- `Исходные данные`
- `Редактор циклического сценария`
- `Набор испытаний`
- `Матрица испытаний` only for the table/screen inside the suite workspace
- `Базовый прогон` / `Опорный прогон`
- `Оптимизация`
- `Анализ результатов`
- `Анимация`
- `Диагностика`
- `Архив диагностики` or `Пакет диагностики SEND`
- `Происхождение данных`
- `Ход выполнения`
- `Цели расчёта`
- `Ограничения`
- `Передать в анализ`
- `Выбрать этот прогон для анализа`

Avoid in user-facing GUI:

- `workspace`
- `contract`
- `legacy`
- `fallback`
- `surface`
- `runtime`
- `handoff`
- `source-of-truth`
- `provenance`
- `manifest`
- `pointer`
- `artifact` / `артефакт`, unless inside technical diagnostics details
- `bundle`, unless paired with clear Russian wording
- `shell`
- `hosted`
- `migration`
- `Desktop Optimizer Center` as a dialog title
- `Compare contract`
- `Открыть выбранный этап`
- `Статус миграции`
- `Данные машины`

## Priority Fix Order

1. Normalize main shell command names and workspace labels so the pipeline is navigated directly, without `Открыть workspace...` and without service terms.
2. Normalize diagnostics labels and progress semantics: one first-class `Собрать диагностику`, same-surface progress, Russian messages.
3. Normalize optimizer visible text: remove `pointer`, `handoff`, `runtime`, English dialog titles, and unclear `contract` wording.
4. Normalize Compare Viewer dock titles/tooltips and visible English strings.
5. Normalize Desktop Mnemo and Animator status texts, preserving working behavior and truthful graphics states.
6. Update tests after text normalization so executable contracts enforce the new user-facing vocabulary rather than the old implementation vocabulary.
