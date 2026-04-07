# RELEASE_NOTES_R31AZ_2026-03-28

## Главное
- Исправлен корень проблемы staged optimization: system influence теперь строится по канонической `model_pneumo_v9_doublewishbone_camozzi.py`, planner потребляет актуальную схему `system_influence.json`, а повторный старт смотрит на `stages_influence.json` вместо битого sentinel `plan.json`.
- Если influence/staging артефакты не создались, staged runner больше не деградирует молча в нулевые alphabetical stages — он пишет явный статус `failed_system_influence` / `failed_param_staging`.
- Собран portable Windows-friendly release zip с коротким путевым бюджетом и без runtime-noise (`runs/`, `send_bundles/`, `workspace/`, `tests/`, `DOCS_SOURCES/`), чтобы убрать ошибки распаковки на Desktop.

## Технически
- `pneumo_solver_ui/calibration/param_staging_v3_influence.py`
- `pneumo_solver_ui/opt_stage_runner_v1.py`
- `pneumo_solver_ui/release_packaging.py`
- `VERSION.txt`
- `release_tag.json`
- `pneumo_solver_ui/release_info.py`
- `BUILD_INFO_LATEST.txt`
- `RELEASE_NOTES_LATEST.txt`

## Acceptance
- targeted pytest: pass
- py_compile: pass
- compileall: pass
