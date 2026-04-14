# Chat Prompt: Engineering Analysis Calibration Influence Center

## Контекст

Расширенные инженерные WEB surfaces для calibration/design/influence/uncertainty должны уйти в отдельный desktop analysis center.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Analysis center должен использовать workspace-first layout: графики, previews, studies и inspectors не прячутся в web-style длинную страницу.
- Левая pane допустима для study tree, comparison tree или object browser только при реальной иерархии; справа должен быть context-sensitive inspector или parameter/details pane.
- Baseline command surface: `menu bar + toolbar + dockable panes + command search + status/progress strip`. `Ribbon` не использовать как default.

## Цель

Перенести в desktop GUI расширенные инженерные surfaces: calibration NPZ, design advisor, system influence, subsystem influence, uncertainty, param influence.

## Можно менять

- новые файлы рядом с lane:
  - `pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
  - `pneumo_solver_ui/desktop_engineering_analysis_model.py`
  - `pneumo_solver_ui/desktop_engineering_analysis_runtime.py`
  - `pneumo_solver_ui/desktop_engineering_analysis_panels.py`
- analysis-specific tests

## Можно читать как источник поведения

- [02_Calibration_NPZ.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/02_Calibration_NPZ.py)
- [03_Design_Advisor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_Design_Advisor.py)
- [03_DesignAdvisor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_DesignAdvisor.py)
- [03_SystemInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_SystemInfluence.py)
- [04_SubsystemsInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_SubsystemsInfluence.py)
- [04_Uncertainty.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_Uncertainty.py)
- [05_ParamInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/05_ParamInfluence.py)
- [05_ParamsInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/05_ParamsInfluence.py)
- [compare_influence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_influence.py)
- [compare_influence_time.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_influence_time.py)

## Нельзя менять

- optimizer center
- desktop input editor
- WEB pages как target

## Правила

- Делай отдельное инженерное окно, а не прячь всё это в optimizer или test center.
- Переносить нужно функциональность и сценарии работы, а не Streamlit layout.
- Analysis center должен быть пригоден для глубокой инженерной работы, а не только для демонстрации графиков.
- Графики, diagnostics и study controls должны поддерживать второй монитор, resize и устойчивую keyboard navigation.

## Готовый промт

```text
Работай только в lane "Engineering Analysis Calibration Influence Center".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: расширенные инженерные WEB surfaces для calibration/design/influence/uncertainty должны уйти в отдельный desktop analysis center.

Цель: перенести в desktop GUI расширенные инженерные surfaces: calibration NPZ, design advisor, system influence, subsystem influence, uncertainty, param influence.

Можно менять только:
- новые desktop_engineering_analysis_* модули
- narrowly related helper modules
- analysis-specific tests

Можно читать как источник поведения:
- pages/02_Calibration_NPZ.py
- pages/03_Design_Advisor.py
- pages/03_DesignAdvisor.py
- pages/03_SystemInfluence.py
- pages/04_SubsystemsInfluence.py
- pages/04_Uncertainty.py
- pages/05_ParamInfluence.py
- pages/05_ParamsInfluence.py
- compare_influence.py
- compare_influence_time.py

Нельзя менять:
- optimizer center
- desktop_input_editor
- WEB pages как target

Правила:
- делай отдельное инженерное окно, а не прячь всё это в optimizer или test center
- переносить нужно функциональность и сценарии работы, а не Streamlit layout
- analysis center должен быть пригоден для глубокой инженерной работы, а не только для демонстрации графиков
- держи chart, preview и study surfaces как first-class рабочие регионы, а не как декоративное приложение к форме
- обеспечь dockable panes, `command search`, keyboard-first navigation и пригодность для второго монитора

Сделай первый или следующий шаг по desktop engineering analysis center.
```
