# Автономные самопроверки

В релизе Testy639 добавлена *быстрая* автономная самопроверка, которая запускается автоматически при старте UI.

## Что запускается автоматически
В `pneumo_solver_ui/pneumo_ui_app.py` сразу после `st.set_page_config(...)`:
- вызывается `pneumo_solver_ui/tools/autoselfcheck.py:ensure_autoselfcheck_once()`
- результат:
  - логируется событием `autoselfcheck` (в JSONL)
  - сохраняется как `autoselfcheck.json` в папке логов (`PNEUMO_LOG_DIR`)

Проверки рассчитаны на **минимальное время выполнения** и работают как smoke‑test:
- `param_contract_check` — базовая проверка корректности/неизменности контракта параметров
- `mech_energy_smoke_check` — быстрая проверка механической модели/энергетики

## Где смотреть результат
- `.../runs/ui_sessions/<UI_...>/logs/autoselfcheck.json`
- в send-bundle zip (файл будет включён автоматически, так как zip собирает папку сессии)

## Как расширять
Если нужно усилить самопроверку:
1) Добавляйте новые lightweight-check функции в `pneumo_solver_ui/tools/autoselfcheck.py`.
2) Соблюдайте правила:
   - не требовать GUI
   - не требовать интернет
   - работать на "чистой" среде
   - давать понятный `summary` + список `failures`
3) Для более тяжёлых прогонов используйте `pneumo_solver_ui/tools/preflight_gate.py` и/или `pneumo_solver_ui/tools/run_autotest.py`.
