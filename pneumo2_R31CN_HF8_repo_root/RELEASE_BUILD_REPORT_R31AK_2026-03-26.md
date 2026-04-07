# RELEASE BUILD REPORT R31AK (2026-03-26)

## Основа
- base package: `PneumoApp_v6_80_R176_R31AI_2026-03-26`
- new package: `PneumoApp_v6_80_R176_R31AK_2026-03-26`

## Изменённые зоны
- `pneumo_solver_ui/npz_bundle.py`
- `pneumo_solver_ui/desktop_animator/app.py`
- `tests/test_r50_animator_dense_export_and_smooth_playback.py`
- release metadata files

## Проверки
- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest: PASS

## Честный статус
Релиз закрывает только следующий шаг по жалобе на высокие скорости: уплотнение animator-facing кадров и smoothing policy playback. Он не объявляет решёнными соседние perf/GL tracks.
