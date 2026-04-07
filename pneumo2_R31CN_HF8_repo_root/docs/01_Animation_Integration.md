# Анимация и Desktop Animator — как пользоваться (интеграция без ручных шагов)

## Быстрый старт (Windows)

1) Запусти `START_PNEUMO_APP.pyw`.
2) Оставь включённой галку **«Запустить Desktop Animator (follow)»**.
3) В браузере откроется UI.
4) В UI:
   - **Simulator → Детальный прогон**
   - включи: ✅ **Auto‑экспорт anim_latest (Desktop Animator)**
   - запусти один детальный прогон.
5) Desktop Animator автоматически подхватит новый `anim_latest` и начнёт показывать анимацию.

Ни батников, ни ручного экспорта.

## Как работает follow‑режим

- UI пишет в `pneumo_solver_ui/workspace/exports/` два файла:
  - `anim_latest.npz` — данные (временные ряды)
  - `anim_latest.json` — pointer (куда смотреть Desktop Animator)

- Desktop Animator запускается как:
```bash
python -m pneumo_solver_ui.desktop_animator.main --follow
```
и периодически проверяет `anim_latest.json`. Если `npz_path` поменялся или файл обновился — автоматически перезагружает данные.

## Ручной экспорт (если нужно)

В UI (после детального прогона) есть раскрывающийся блок:
**«🖥 Desktop Animator (внешнее окно)»** → кнопка **«Экспортировать anim_latest сейчас»**.

Это полезно, если:
- вы загрузили лог из кэша и не запускали вычисления;
- вы отключили авто‑экспорт.

## Важный момент про «скорость соответствует расчёту»

В Web‑3D (вкладка **Анимация → Механика → 3D**) траектория теперь по умолчанию строится по выходам модели:
- `скорость_vx_м_с`
- `yaw_рад`

Это делает «изгиб дороги/повороты» и скорость **согласованными с расчётом**, а не демо‑кривой.

Если вы хотите включить демо‑режимы (слалом, радиус и т.п.) — включите чекбокс выбора траектории.

## Где лежит код

- Экспорт NPZ: `pneumo_solver_ui/npz_bundle.py`
- Desktop Animator:
  - `pneumo_solver_ui/desktop_animator/main.py` (CLI, follow‑режим)
  - `pneumo_solver_ui/desktop_animator/app.py` (GUI)
- Интеграция в UI:
  - `pneumo_solver_ui/pneumo_ui_app.py`
  - `pneumo_solver_ui/pages/07_DesktopAnimator.py`
- One-click launcher:
  - `START_PNEUMO_APP.pyw`

## Troubleshooting

- Animator запустился, но «пусто»:
  - проверь `pneumo_solver_ui/workspace/exports/anim_latest.npz` и `anim_latest.json`
  - проверь, что запускался **детальный** прогон
  - если нужен воздух/клапана/давления — включи `record_full` (UI покажет предупреждение, если он выключен)

- Если окно Animator «моргает»/падает на некоторых GPU:
  - в лаунчере включи **Animator --no-gl**
  - или при запуске `--no-gl`
