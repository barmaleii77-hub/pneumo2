# Структура проекта

Ниже — карта папок/файлов в релизе **R25**.

## Корень архива

Тут лежит всё, что нужно для «один клик»:

- `README.md` — быстрый вход (как поставить/запустить, где логи, что нового).
- `INSTALL_WINDOWS.bat` — установка зависимостей в `.venv`.
- `RUN_WINDOWS.bat` — запуск Streamlit UI.
- `START_PNEUMO_UI_CONSOLE.bat` — запуск UI с консолью (удобно смотреть сообщения).
- `START_PNEUMO_UI.pyw` — запуск UI без консоли (удобно, если консоль раздражает).

## Папка `pneumo_solver_ui/`

Это **само приложение** (UI + модель + скрипты). Основные элементы:

### Главный UI
- `pneumo_ui_app.py` — Streamlit‑приложение.
  - Baseline (быстрый прогон тест‑сьюта)
  - Графики и анимация 2D/3D
  - Оптимизация (фоновые прогоны)
  - Экспорты и диагностика
  - Калибровка/Autopilot по NPZ (в expander)

### Модель
- `model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py` — основная модель (пневматика + энергия + «мягкие» патчи/защиты).

### Оптимизация / «автопилот» в терминах оптимизации
- `opt_worker_v3_margins_energy.py` — «целевая функция» и логика оценки кандидата (метрики, штрафы, энергетика, ограничения).

### Компоненты визуализации
- `mech_anim_fallback.py` — fallback‑анимация на Matplotlib (работает, даже если кастомные JS‑компоненты не поднялись).
- `components/` — HTML‑компоненты (SVG/Canvas). В R25 это основной (дефолтный) режим для 2D/3D: Play выполняется в браузере без server‑rerun на каждый кадр. Если компоненты не грузятся — переключайся на `mech_anim_fallback.py`.

### Калибровка по логам (NPZ)
- `calibration/` — пакет утилит:
  - `pipeline_npz_oneclick_v1.py` — «oneclick» pipeline (проверка NPZ, подсказка маппинга, подготовка артефактов).
  - `pipeline_npz_autopilot_v19.py` — autopilot‑pipeline (более автоматический режим).
  - `npz_autosuggest_mapping_v2.py` — анализ NPZ и подсказка маппинга.
  - `osc_csv_to_npz_v1.py` — конвертация CSV‑пакета в NPZ (если CSV в ожидаемом «пакетном» формате).

### Tools / Диагностика
- `tools/run_full_diagnostics.py` — генератор диагностического ZIP (self_check + baseline + окружение + логи + optional NPZ‑pipelines).

### Папки с данными, которые создаются во время работы

- `logs/` — логи UI и метрики (jsonl):
  - `ui_*.log` — основные события UI (start, baseline, detail, exports, errors)
  - `ui_combined.log` — единый сквозной лог
  - `metrics_combined.jsonl` — единый сквозной jsonl
  - `metrics_*.jsonl` — периодические метрики процесса (CPU/RAM)

- `results/` — результаты оптимизаций/прогонов (CSV и вспомогательные файлы).

- `workspace/` — «рабочая зона» для артефактов:
  - `workspace/osc/` — NPZ/CSV «осциллограммы» (в том числе экспорт из baseline → `T01_osc.npz`, `T02_osc.npz` ...)
  - `workspace/exports/` — ZIP‑диагностики, которые создаются прямо из UI

- `calibration_runs/` — результаты запусков калибровки/автопилота (oneclick/autopilot) из UI или из bat‑скриптов

## Где что искать, если надо «быстро»

- **Не работает Play / кажется бесконечным** → см. `mech_anim_fallback.py` + `docs/03_Troubleshooting.md`.
- **Нужен NPZ для калибровки** → `docs/05_WhatIs_NPZ.md` + UI expander «Калибровка и Autopilot (NPZ/CSV)».
- **Нужно собрать ZIP для отправки** → UI expander «Диагностика (ZIP для отправки)» или `tools/run_full_diagnostics.py`.
