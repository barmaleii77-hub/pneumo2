# RELEASE_BUILD_REPORT_R31AI_2026-03-26

## База

- Исходная база: `PneumoApp_v6_80_R176_R31AH_2026-03-26`
- Новый релиз: `PneumoApp_v6_80_R176_R31AI_2026-03-26`

## Основание для патча

Свежий SEND bundle на R31AH подтвердил два факта:

- live 3D ловит реальные `OpenGL GLError` во время манипуляции окнами;
- playback cadence при `visible_aux >= 10` деградирует примерно до `0.9–1.0 Hz`.

Это и стало основанием для Desktop Animator patch-pass в R31AI.

## Изменённые файлы

См. `CHANGED_FILES_R31AI_2026-03-26.txt`.

## Проверки

- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest slice: PASS

## Артефакты

- `RELEASE_NOTES_R31AI_2026-03-26.md`
- `BUNDLE_ANALYSIS_R31AH_PLAYBACK_AND_LAYOUT_2026-03-26.md`
- `BUNDLE_ANALYSIS_R31AH_PLAYBACK_AND_LAYOUT_2026-03-26.json`
- `TODO_WISHLIST_R31AI_ADDENDUM_2026-03-26.md`
- `PYCHECKS_R31AI_2026-03-26.log`
- `COMPILEALL_R31AI_2026-03-26.log`
- `PYTEST_TARGETED_R31AI_2026-03-26.log`
