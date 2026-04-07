# Merge manifest (история сборки)

Цель: собрать множество вариантов/патчей в **одно** приложение, где:
- baseline/детальные логи/оптимизация живут в одном UI,
- есть диагностика (zip-пакет),
- требования/бэклог хранятся рядом с кодом,
- любые регрессии (NameError, session_state conflicts, rerun-loops) ловятся до релиза.

## Источники (основные)
- R35 → R40: последовательные фиксы UI/анимации/кэша/диагностики.
- Контекст требований: `docs/context/*` (txt/mhtml) + `WISHLIST.md/json` + `PROJECT_CONTEXT_ANALYSIS.md`.

## Что считаем «каноничным» сейчас
- Главный UI: `pneumo_solver_ui/pneumo_ui_app.py`
- Модель по умолчанию: `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`
- Диагностика: `pneumo_solver_ui/tools/run_full_diagnostics.py`

## Политика мержа
- Любой фикс должен быть:
  1) подтверждён логами/диагностикой,
  2) описан в `docs/00_ReleaseNotes.md` + отдельный `docs/RELEASE_NOTES_Rxx.md`,
  3) закреплён патчем в `diffs/`.

