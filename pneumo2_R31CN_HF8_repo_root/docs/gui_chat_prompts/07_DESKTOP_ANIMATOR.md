# Chat Prompt: Desktop Animator

## Канонический слой

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/context/gui_spec_imports/v3/ui_element_catalog.csv`
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv`
- `docs/context/gui_spec_imports/v3/acceptance_criteria.csv`
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv`
- `docs/context/gui_spec_imports/v3/docking_matrix.csv`

## Цель lane

Развивать `Desktop Animator` как отдельное viewport-first окно инженерной
анимации и visual inspection.

## Можно менять

- `pneumo_solver_ui/desktop_animator/*`
- animator-specific tests

## Можно читать как источник поведения

- `pneumo_solver_ui/animation_cockpit_web.py`
- `pneumo_solver_ui/pages/11_AnimationCockpit_Web.py`
- `pneumo_solver_ui/anim_export_meta.py`
- `pneumo_solver_ui/ring_visuals.py`
- `pneumo_solver_ui/ui_animation_results_*`

## Нельзя менять

- desktop shell;
- compare viewer;
- desktop mnemo;
- web pages как target.

## Правила

- Animator остаётся специализированным standalone app.
- Truth-state banner обязателен: `расчетно подтверждено / по исходным данным / условно`.
- Source marker и build time для расчетных представлений обязательны.
- Animator не переносится в shell как embedded giant panel.
