# Obobshchenie R40 — Release Notes

Дата: 2026-01-24

## TL;DR

- В проект добавлен ваш **актуальный бэклог/требования** из `WISHLIST.md/.json`.
- Усилена диагностика: добавлены **static checks** (compileall + ruff F821/undefined names).
- В runtime‑зависимости добавлен `requests` (нужен диагностике для HTTP/UI‑проверок).
- Обновлены bat‑скрипты и версия приложения (APP_RELEASE=R40).

## Детали изменений

### 1) Встраивание WISHLIST в контекст/документацию

Добавлены файлы:
- `docs/context/WISHLIST.md` — ваш актуальный «живой» список требований и приоритетов.
- `docs/WISHLIST.json` — машинная структура (epics, design variables, minimum outputs, backlog).
- `docs/12_Wishlist.md` — как это использовать в проекте.

Это решает проблему «требования разбросаны по переписке/логам/релизам». Теперь источник требований лежит рядом с кодом.

### 2) Static checks в полной диагностике

В `pneumo_solver_ui/tools/run_full_diagnostics.py` добавлены:
- `python -m compileall -q pneumo_solver_ui` — быстрый компиляционный smoke‑test.
- `python -m ruff check pneumo_solver_ui --select F821` — ловит *undefined names* (частая причина ваших падений вида `NameError: ... is not defined`).

Результаты пишутся в `RUN_*/static_checks/` и попадают в диагностический ZIP.

### 3) requests в зависимостях

Так как диагностика делает HTTP‑проверки (`requests.get(...)`), `requests` добавлен в `pneumo_solver_ui/requirements.txt`.

### 4) Обновление bat‑скриптов и версий

- `INSTALL_WINDOWS.bat`, `RUN_WINDOWS.bat` обновлены на подпись R40.
- В UI обновлён `APP_RELEASE = "R40"`.

## Диффы/патчи

В этом релизе добавлен патч:
- `diffs/R40_from_R39.patch` — изменения R40 поверх R39.

Старые патчи (от предыдущих релизов) сохранены:
- `diffs/R39_from_R38.patch`
- `diffs/R39_from_R35.patch`

## Что дальше (следующий шаг)

1) Пройти по `docs/context/WISHLIST.md` и превратить приоритетные требования в:
   - измеряемые критерии,
   - тест‑кейсы,
   - список design variables для оптимизатора.
2) Разделить требования на уровни:
   - UI/UX (наблюдаемость/удобство),
   - матмодель (физика/правильность),
   - оптимизация (стратегия/этапы).

