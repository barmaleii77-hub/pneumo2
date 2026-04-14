# Chat Prompt: Desktop Mnemo

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v3/ui_element_catalog.csv`
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/desktop_web_parity_map.json`

## Цель lane

Развивать `Desktop Mnemo` как отдельное специализированное окно схемы и
мнемосхемы, а не как embedded-дубль shell или animator.

## Можно менять

- `pneumo_solver_ui/desktop_mnemo/*`
- mnemo-specific tests

## Можно читать как источник поведения

- `pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py`
- `pneumo_solver_ui/scheme_integrity.py`
- `pneumo_solver_ui/ui_svg_*`
- `pneumo_solver_ui/validation_cockpit_web.py`

## Нельзя менять

- desktop shell;
- desktop input editor;
- compare viewer;
- desktop animator;
- web pages как target.

## Правила

- Mnemo остаётся отдельным окном.
- Не дублировать animator и compare viewer.
- Follow-mode, pinned nodes, diagnostics overlays и truth markers должны
  оставаться честными и context-aware.
