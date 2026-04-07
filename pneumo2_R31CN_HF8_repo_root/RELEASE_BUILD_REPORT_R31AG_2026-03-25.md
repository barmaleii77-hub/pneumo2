# RELEASE BUILD REPORT — R31AG (2026-03-25)

Release: `PneumoApp_v6_80_R176_R31AG_2026-03-25`

## Изменённые ключевые файлы
- `pneumo_solver_ui/data_contract.py`
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
- `pneumo_solver_ui/desktop_animator/app.py`
- `pneumo_solver_ui/components/mech_car3d/index.html`
- `pneumo_solver_ui/components/mech_anim/index.html`
- `pneumo_solver_ui/components/mech_anim_quad/index.html`
- `pneumo_solver_ui/components/corner_heatmap_live/index.html`
- `pneumo_solver_ui/components/minimap_live/index.html`
- `pneumo_solver_ui/components/road_profile_live/index.html`
- `pneumo_solver_ui/components/pneumo_svg_flow/index.html`
- `pneumo_solver_ui/components/playhead_ctrl/index.html`
- `tests/test_r44_cylinder_packaging_contract_and_animator.py`
- `tests/test_r31ag_animator_regressions_and_web_idle.py`

## Проверки
- `py_compile`: PASS
- `compileall`: PASS
- extracted JS `<script>` syntax via `node --check`: PASS
- targeted pytest slice: PASS

## Смысл релиза
- вернуть видимую дорогу в Desktop Animator после regression path из R31AF;
- перевести цилиндры на fixed-body packaging вместо full pin-to-pin shell;
- перестать душить front/rear graphics playback perf-mode'ом;
- убрать persistent idle render-loop tail в Web UI heavy followers.
