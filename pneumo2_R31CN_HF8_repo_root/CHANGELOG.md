## R31P — 2026-03-24
- Desktop Animator no longer floats the 3D GL dock during detached/tiled layout on GL builds; fix motivated by the Windows manual SEND bundle crash.
- strict loglint seq validation is now pid-aware for multi-process session logs.

# Changelog — Animatsiya (v6_80 series)


## R31O (2026-03-23)
- Ring generator now keeps authored raw `zL_m/zR_m` intact for preview/summary and builds `zL_closed_m/zR_closed_m` separately for periodic export.
- Periodic phased SINE no longer gets a false seam-slope correction from coarse edge derivatives.
- Active ring UI removes the last deprecated `use_container_width` call.
- TODO/WISHLIST refreshed with the new raw-vs-closed ring truth split and remaining release-gate items.

## Animatsiya680R015 (2026-02-18)
- Исправлено: краш Desktop Animator при старте/первом кадре — `RoadHudWidget` использовал `self.geom`, но поле не было инициализировано.
  - Добавлен безопасный дефолт `ViewGeometry()` + метод `set_geometry()`.
  - `CockpitWidget.set_bundle()` теперь передаёт геометрию в Road HUD.
- Исправлено: типичный сценарий «всё красное» из-за занятого порта Streamlit.
  - Лаунчер больше не «прицепляет» браузер к старому инстансу на занятом порту.
  - Теперь автоматически подбирается следующий свободный порт (8505 → 8506 → ...), и порт обновляется в GUI лаунчера.
- Улучшено: запуск Desktop Animator из веб‑UI.
  - На Windows используется pythonw.exe из **того же venv**, если доступен.
  - stdout/stderr Desktop Animator теперь пишутся в `PNEUMO_LOG_DIR/desktop_animator.log` (важно для pythonw.exe).
- Добавлено: видимая в GUI индикация и окно отчёта **«Самопроверки»**.
  - Самопроверки реально запускаются при загрузке anim_latest.npz.
  - В отчёт включена жёсткая проверка: все `segment_id` должны быть описаны в `meta_json.road.segments` (с перечислением пропусков).


## Animatsiya680R014 (2026-02-18)
- Исправлено: **ImportError при старте UI** — `from pneumo_solver_ui.run_registry import get_status`.
  - В `pneumo_solver_ui/run_registry.py` добавлен лёгкий `get_status(kind)` (best-effort),
    читающий pointer‑файлы последнего прогона из `WORKSPACE_DIR/cache/**`.
  - В `app.py` импорт сделан устойчивым: вместо импорта символа используется импорт модуля
    и `getattr()` + fallback‑реализация. Теперь отсутствие helper‑функции **не должно ломать запуск**.


## Animatsiya680R013 (2026-02-18)
- Улучшено: `ui_router.py` теперь **не просто пишет “страница недоступна”**, а:
  - логирует исключение в диагностический eventlog (`ui_page_exception`),
  - даёт кнопку **«Сформировать диагностику»** и **скачивание ZIP** прямо на экране ошибки (без поиска кнопки в сайдбаре).
- Улучшено: корневой `app.py` стал более устойчивым к проблемам импорта (и запуску не из корня проекта):
  - автоматически добавляет `REPO_ROOT` в `sys.path`,
  - защищает импорты внутренних модулей и показывает понятное сообщение вместо «всё красное».
- Совместимость: `ui_st_compat.py` расширен поддержкой `st.data_editor` (width="stretch" ↔ use_container_width).


## Animatsiya680R012 (2026-02-18)
- Исправлено: веб‑UI больше не падает «всё красное» на несовпадающих версиях Streamlit (width="stretch" vs use_container_width).
  Добавлен/включён ранний compat‑слой `pneumo_solver_ui/ui_st_compat.py`.
- Улучшено: `Setup` (00_Setup) теперь разделяет критичные и опциональные зависимости: критичные — `error`, опциональные — `warning`.
- Технически: compat включается в `ui_bootstrap.py` и при прямом запуске `pneumo_ui_app.py`.

Формат: `Animatsiya680R###`.

## Animatsiya680R011 (2026-02-18)
- Исправлено: жёсткий self-check **segment_id → meta_json['road']['segments']** теперь реально исполняется и корректно поднимает `FAIL` с перечислением пропущенных ID.
- Исправлено: совместимость чтения `scenario_json` (spec в корне или в `{"spec": ...}`) для:
  - извлечения метаданных сегментов при экспорте (`npz_bundle.py`),
  - построения label_func и границ сегментов (`opt_worker_v3_margins_energy.py`).
- Добавлено: `pneumo_solver_ui/scenario_io.py` — единый helper для чтения scenario_json.
- Документация: обновлён `DATA_CONTRACT_UNIFIED_KEYS.md` (сегменты + правило self-check).

## Animatsiya680R010
- Добавлено/улучшено: экспорт сегментов в meta_json (`road.segments`) при наличии `scenario_json`.
- Добавлено: жёсткая self-check проверка консистентности segment_id ↔ road.segments (в R011 исправлено исполнение/детализация).
- Улучшено: дорожная лента/подсветка сегментов (приглушённая, без «гирлянд»).

## Animatsiya680R001–R009
- Итеративные улучшения Desktop Animator: компоновка окон, режим повтора Play, отрисовка дороги, ракурсные виды 2D/3D,
  подсказки/оверлеи параметров и базовые self-checks.
