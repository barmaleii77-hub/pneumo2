# Chat Prompt: Diagnostics And Send Bundle Center

## Контекст

WEB-страницы диагностики и send bundle больше не должны быть основным рабочим местом. Пользователь должен собирать, проверять и отправлять bundle из нормального desktop GUI.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Diagnostics center может быть utility-oriented, но всё равно обязан соблюдать keyboard-first, accessibility, High-DPI и performance policy.
- Baseline command surface остаётся `menu/toolbar/panes/search/status`; критичные ошибки и blocking conditions нельзя прятать только в status bar.
- Diagnostics должны оставаться first-class operational surface: `Собрать диагностику`, bundle contents, latest ZIP path, self-check, freshness и autosave on exit/crash видимы в UI.

## Цель

Сделать единый desktop GUI diagnostics/send center без WEB. Пользователь должен уметь запускать полную диагностику, собирать bundle, смотреть summary, inspect, health и отправку результатов из desktop flow.

## Можно менять

- [run_full_diagnostics_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/run_full_diagnostics_gui.py)
- [send_results_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_results_gui.py)
- новые файлы рядом с lane:
  - `pneumo_solver_ui/tools/desktop_diagnostics_center.py`
  - `pneumo_solver_ui/desktop_diagnostics_model.py`
  - `pneumo_solver_ui/desktop_diagnostics_runtime.py`
- desktop diagnostics/send tests

## Можно читать как источник поведения

- [99_Diagnostics.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/99_Diagnostics.py)
- [98_BuildBundle_ZIP.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/98_BuildBundle_ZIP.py)
- [98_SendBundle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/98_SendBundle.py)
- [diagnostics_entrypoint.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/diagnostics_entrypoint.py)
- [diagnostics_unified.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/diagnostics_unified.py)
- [send_bundle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/send_bundle.py)
- [send_bundle_contract.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_bundle_contract.py)
- [inspect_send_bundle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/inspect_send_bundle.py)
- [health_report.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/health_report.py)

## Нельзя менять

- [test_center_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/test_center_gui.py) кроме явной интеграции
- [desktop_input_editor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py)
- [qt_compare_viewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py)
- WEB pages как target

## Правила

- Не дублируй WEB pages один в один, строй нормальный desktop operator flow.
- Выноси summary/runtime helpers в отдельные модули при росте сложности.
- Сохрани hosted/standalone compatibility.
- Diagnostic path должен быть machine-readable, а не только “кнопка и текст”.

## Готовый промт

```text
Работай только в lane "Diagnostics And Send Bundle Center".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: WEB diagnostics/send bundle workflow больше не должен быть главным. Нужен единый desktop GUI для диагностики, проверки bundle и отправки результатов.

Цель: сделать desktop diagnostics/send center без WEB. Пользователь должен уметь запускать полную диагностику, собирать bundle, смотреть summary, inspect, health и отправку результатов из desktop flow.

Можно менять только:
- pneumo_solver_ui/tools/run_full_diagnostics_gui.py
- pneumo_solver_ui/tools/send_results_gui.py
- новые desktop_diagnostics_* модули
- diagnostics/send desktop tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/99_Diagnostics.py
- pneumo_solver_ui/pages/98_BuildBundle_ZIP.py
- pneumo_solver_ui/pages/98_SendBundle.py
- pneumo_solver_ui/diagnostics_entrypoint.py
- pneumo_solver_ui/diagnostics_unified.py
- pneumo_solver_ui/send_bundle.py
- pneumo_solver_ui/tools/send_bundle_contract.py
- pneumo_solver_ui/tools/inspect_send_bundle.py
- pneumo_solver_ui/tools/health_report.py

Нельзя менять:
- test_center_gui.py кроме явной интеграции
- desktop_input_editor.py
- qt_compare_viewer.py
- WEB pages как target

Правила:
- не дублируй WEB pages один в один, строй нормальный desktop operator flow
- выноси summary/runtime helpers в отдельные модули при росте сложности
- сохрани hosted/standalone compatibility
- diagnostic path должен быть machine-readable, а не только “кнопка и текст”

Сделай следующий шаг по diagnostics/send desktop center и прогони targeted tests.
```
