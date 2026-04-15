# Chat Prompt: Оптимизатор Со Всеми Настройками

## Канонический слой

- Сначала читать [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md),
  затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Общий detailed layer для shell, migration и observability:
  [gui_spec_imports/v3/README.md](../context/gui_spec_imports/v3/README.md).
- Historical design-recovery precursor для optimization contract:
  [optimization_control_plane_contract_v12.json](../context/gui_spec_imports/v12_design_recovery/optimization_control_plane_contract_v12.json),
  [pneumo_gui_codex_spec_v12_design_recovery.json](../context/gui_spec_imports/v12_design_recovery/pneumo_gui_codex_spec_v12_design_recovery.json).

## Контекст

Optimization workflow больше не должен быть завязан на WEB. Нужен полноценный desktop optimizer center для operator workflow и всех инженерных настроек.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Optimizer center должен наследовать baseline `menu/toolbar/panes/search/status`, а не web-first layout.
- Даже если optimizer workspace не выглядит как классический CAD viewport, он обязан сохранять keyboard-first, accessibility, High-DPI и performance policy. `Ribbon` не использовать как default.
- В optimizer UI должен быть один active mode selector, видимые `objective stack` и `hard gate`, явный baseline source и без двух конкурирующих launch-кнопок.
- `v12` считается важным precursor-слоем для optimization control plane: он фиксирует design-first требования до любых implementation-pass слоёв.

## Цель

Перенести optimization workflow из WEB в полноценный desktop GUI center. Нужны: scope, search space, objectives, stage policy, distributed settings, runtime launch, live progress, history, finished jobs, handoff, packaging, objective contract.

## Можно менять

- новые GUI файлы:
  - `pneumo_solver_ui/tools/desktop_optimizer_center.py`
  - `pneumo_solver_ui/desktop_optimizer_model.py`
  - `pneumo_solver_ui/desktop_optimizer_runtime.py`
  - `pneumo_solver_ui/desktop_optimizer_panels.py`
  - `pneumo_solver_ui/desktop_optimizer_tabs/*`
- optimization-specific desktop tests
- shell adapter/catalog only if adding new optimizer window

## Можно читать как источник поведения

- [03_Optimization.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_Optimization.py)
- [04_DistributedOptimization.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_DistributedOptimization.py)
- [04_DistributedOptimization_R58.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_DistributedOptimization_R58.py)
- [30_Optimization.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/30_Optimization.py)
- все `optimization_*.py`
- [opt_stage_runner_v1.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/opt_stage_runner_v1.py)
- [opt_worker_v3_margins_energy.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/opt_worker_v3_margins_energy.py)
- [ui_optimization_page_shell_helpers.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_optimization_page_shell_helpers.py)

## Нельзя менять

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- desktop input editor
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages как target

## Правила

- Optimization GUI дели по панелям и вкладкам.
- Не тащи сюда WEB view code напрямую, переносить нужно поведение и shared runtime logic.
- Избегай нового гигантского single-file optimizer window.

## Готовый промт

```text
Работай только в lane "Оптимизатор Со Всеми Настройками".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: optimization workflow уходит из WEB. Нужен полноценный desktop optimizer center для operator workflow и всех инженерных настроек.

Цель: перенести optimization workflow из WEB в полноценный desktop GUI center. Нужны: scope, search space, objectives, stage policy, distributed settings, runtime launch, live progress, history, finished jobs, handoff, packaging, objective contract и operator-oriented UX.

Можно менять только:
- новые desktop_optimizer_* модули
- optimization-specific desktop tests
- shell adapter/catalog only if adding new optimizer window

Можно читать как источник поведения:
- pneumo_solver_ui/pages/03_Optimization.py
- pneumo_solver_ui/pages/04_DistributedOptimization.py
- pneumo_solver_ui/pages/04_DistributedOptimization_R58.py
- pneumo_solver_ui/pages/30_Optimization.py
- все optimization_*.py
- pneumo_solver_ui/opt_stage_runner_v1.py
- pneumo_solver_ui/opt_worker_v3_margins_energy.py
- pneumo_solver_ui/ui_optimization_page_shell_helpers.py

Нельзя менять:
- pneumo_ui_app.py
- desktop_input_editor.py
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages как target

Правила:
- optimization GUI дели по панелям и вкладкам
- не тащи сюда WEB view code напрямую, переносить нужно поведение и shared runtime logic
- избегай нового гигантского single-file optimizer window

Сделай первый или следующий логичный шаг по desktop optimizer center и сохрани модульность.
```
