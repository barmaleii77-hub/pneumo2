# Chat Prompt: Центр оптимизации

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`, раздел `К. Базовый прогон, оптимизация и анализ`
- `docs/context/gui_spec_imports/v3/pneumo_gui_codex_spec_v3_refined.json`
- `docs/context/gui_spec_imports/v3/help_catalog.csv`
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/gui_spec_imports/v3/pipeline_observability.csv`
- `docs/context/desktop_web_parity_map.json`

## Цель lane

Собрать единый solve-center для operator workflow и инженерных настроек
оптимизации.

На активном экране всегда видны:

- active mode;
- objective contract;
- hard gate;
- baseline source;
- auto-update baseline;
- current stage и stage budget;
- candidate counts, underfill и gate reasons;
- run directory и latest results file.

## Можно менять

- `pneumo_solver_ui/tools/desktop_optimizer_center.py`
- `pneumo_solver_ui/desktop_optimizer_model.py`
- `pneumo_solver_ui/desktop_optimizer_runtime.py`
- `pneumo_solver_ui/desktop_optimizer_panels.py`
- `pneumo_solver_ui/desktop_optimizer_tabs/*`
- optimizer-specific desktop tests

## Можно читать как источник поведения

- `pneumo_solver_ui/pages/03_Optimization.py`
- `pneumo_solver_ui/pages/04_DistributedOptimization.py`
- `pneumo_solver_ui/pages/30_Optimization.py`
- `pneumo_solver_ui/opt_stage_runner_v1.py`
- `pneumo_solver_ui/opt_worker_v3_margins_energy.py`

## Нельзя менять

- `pneumo_solver_ui/pneumo_ui_app.py` как target surface;
- desktop input editor;
- compare viewer;
- animator;
- mnemo;
- web pages как target.

## Правила

- На экране одновременно не существует двух главных кнопок запуска.
- `StageRunner` — рекомендуемый режим, distributed coordinator — advanced.
- Advanced distributed/cluster-настройки живут внутри того же solve-center, а не на параллельной странице.
- Optimization GUI делится на панели и табы, а не врастает в single-file window.
