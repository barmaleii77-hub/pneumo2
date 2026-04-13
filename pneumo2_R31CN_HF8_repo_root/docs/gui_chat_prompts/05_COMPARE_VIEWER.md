# Chat Prompt: Compare Viewer

## Контекст

`qt_compare_viewer` должен стать главным специализированным окном сравнения и постепенно забрать compare/results/validation use-cases из WEB.

## Цель

Сделать `qt_compare_viewer` основным специализированным GUI сравнения и постепенно поглотить compare/results/validation сценарии, которые раньше жили в WEB.

## Можно менять

- [qt_compare_viewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py)
- compare-specific helper modules рядом с ним
- compare-specific tests

## Можно читать как источник поведения

- [compare_npz_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_npz_web.py)
- [compare_npz.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_npz.py)
- [compare_session.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_session.py)
- [compare_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_ui.py)
- [validation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/validation_cockpit_web.py)
- [12_ResultsViewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/12_ResultsViewer.py)
- [20_CompareRuns.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/20_CompareRuns.py)
- [21_CompareRuns_Quick.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/21_CompareRuns_Quick.py)
- `ui_results_*` helpers

## Нельзя менять

- desktop shell
- desktop animator
- desktop mnemo
- WEB compare pages как target

## Правила

- Treat `qt_compare_viewer` as standalone specialized app.
- Не распыляйся на shell и WEB.
- Переносить именно рабочие compare/results функции, а не просто тексты.

## Готовый промт

```text
Работай только в lane "Compare Viewer".

Контекст: qt_compare_viewer должен стать главным специализированным окном сравнения. WEB compare/results/validation surfaces используются только как источник поведения.

Цель: сделать qt_compare_viewer основным специализированным GUI сравнения и постепенно поглотить compare/results/validation сценарии, которые раньше жили в WEB.

Можно менять только:
- pneumo_solver_ui/qt_compare_viewer.py
- compare-specific helper modules рядом с ним
- compare-specific tests

Можно читать как источник поведения:
- pneumo_solver_ui/compare_npz_web.py
- pneumo_solver_ui/compare_npz.py
- pneumo_solver_ui/compare_session.py
- pneumo_solver_ui/compare_ui.py
- pneumo_solver_ui/validation_cockpit_web.py
- pneumo_solver_ui/pages/12_ResultsViewer.py
- pneumo_solver_ui/pages/20_CompareRuns.py
- pneumo_solver_ui/pages/21_CompareRuns_Quick.py
- pneumo_solver_ui/ui_results_* helpers

Нельзя менять:
- desktop_shell/*
- desktop_animator
- desktop_mnemo
- WEB compare pages как target

Правила:
- treat qt_compare_viewer as standalone specialized app
- не распыляйся на shell и WEB
- переносить именно рабочие compare/results функции, а не просто тексты

Сделай следующий локальный шаг по compare viewer и проверь его targeted tests.
```
