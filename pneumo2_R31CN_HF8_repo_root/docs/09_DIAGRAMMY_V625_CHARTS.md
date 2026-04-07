# Diagrammy: Comparative Charts Upgrade for UnifiedPneumoApp v6.25 (WINSAFE)

Этот пакет — **полная рабочая версия приложения поверх базы** `UnifiedPneumoApp_UNIFIED_v6_25_WINSAFE` с фокусом на **сравнительные диаграммы**, **нулевую базовую позу для перемещений (display-only)** и **единообразные масштабы** в веб‑интерфейсе и в отдельном окне под Windows (Qt).

Ключевая цель: быстрее и надёжнее сравнивать результаты расчётов (несколько прогонов `.npz`) — наложением, Δ‑сравнением, с одинаковыми шкалами и удобной навигацией.

---

## Что сделано

### 1) Web: новая страница **Compare NPZ (Web)**
Файл: `pneumo_solver_ui/pages/06_CompareNPZ_Web.py`

В Streamlit добавлена полноэкранная страница сравнения `.npz`:

- выбор папки с `.npz` (обычно `pneumo_solver_ui/workspace/exports` или `.../osc`)
- мультивыбор прогонов и выбор *reference* (базового) прогона
- выбор таблицы: `main / p / q / open`
- выбор сигналов + быстрый фильтр по имени
- **Overlay** (наложение) или **Δ to reference** (разности относительно reference)
- **Zero baseline** (для displacement/angle) — приводим «нулевую позицию» к состоянию в начале (или медиане окна)
- **Единицы и читаемость**: mm/m и deg/rad
- **Lock Y**: одинаковая шкала по Y на каждом сигнале для всех прогонов
- **Lock Y by unit**: одинаковая шкала по Y для всех выбранных сигналов одной физической размерности
- **Symmetric Y**: симметрия шкалы относительно 0 (удобно для Δ и «обнулённых» перемещений)
- playhead‑ползунок + вертикальная линия‑маркер
- тепловая карта **max |Δ|** (Runs × Signals) — быстрый обзор «где отличия максимальны»

### 2) Qt (Windows): улучшен **Compare Viewer (QT)**
Файл: `pneumo_solver_ui/qt_compare_viewer.py`

Добавлены опции, которые приводят GUI к той же логике сравнения, что и Web:

- **Zero baseline** для перемещений/углов (display‑only)
- **Baseline window (s)**: t0 или медиана первого окна
- **Distance / Angle units**: mm/m и deg/rad
- **Lock Y** и **Lock Y by unit**
- **Symmetric Y around 0**
- улучшен режим **Δ to reference**: теперь reference отображается как «0 линия», а остальные прогоны как Δ‑кривые

GUI остаётся приоритетным: для быстрой инженерной работы и навигации (playhead, crosshair, linked‑x) — он удобнее.

### 3) Единицы/преобразования: исправлена ошибка в `_infer_unit_and_transform`
Файл: `pneumo_solver_ui/compare_ui.py`

- исправлено неверное обращение с `_mm` (раньше ошибочно умножалось на 1000)
- пересчёт **Pa → bar** приведён к стандарту `1 bar = 100000 Pa` (а не деление на 101325)
- добавлены управляемые конверсии `dist_unit` и `angle_unit`

### 4) Web‑рендеринг графиков: исправлены fallback‑обёртки Streamlit/Plotly
Файлы:
- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/param_influence_ui.py`

Исправлено: на старых/разных версиях Streamlit параметр `width='stretch'` может отсутствовать — теперь есть корректный fallback на `use_container_width=True`.

### 5) Анимация: базовая поза как «ноль» для roll/pitch и визуальный контроль mid‑stroke
Файлы:
- `pneumo_solver_ui/components/mech_anim/index.html`
- `pneumo_solver_ui/components/mech_car3d/index.html`

Сделано:
- **roll/pitch (phi/theta)** показываются относительно начального состояния (t0 → 0°)
- в 2D‑анимации для штоков добавлен **процент хода** и цветовая индикация близости к 50% (mid‑stroke)
- в 3D‑анимации roll/pitch и высота кузова отображаются относительно t0 (display‑only)

---

## Как запустить

### Веб (Streamlit)
1) Установить зависимости (как в основном README проекта)
2) Запуск:

```bash
streamlit run app.py
```

3) Открыть страницу **“Compare NPZ (Web)”**

### GUI (Qt)
1) В веб‑приложении открыть страницу **“Compare Viewer (QT)”**
2) В появившемся окне выбрать папку с `.npz`, отметить нужные прогоны и сигналы.

---

## Где что лежит

- **Web compare**: `pneumo_solver_ui/pages/06_CompareNPZ_Web.py`
- **Qt compare viewer**: `pneumo_solver_ui/qt_compare_viewer.py`
- **Загрузка/парсинг npz**: `pneumo_solver_ui/compare_ui.py`
- **fix Streamlit Plotly wrapper**: `pneumo_solver_ui/pneumo_ui_app.py`, `pneumo_solver_ui/param_influence_ui.py`
- **анимация 2D/3D**: `pneumo_solver_ui/components/mech_anim/`, `pneumo_solver_ui/components/mech_car3d/`

---

## Диффы и патчи

- Список изменённых файлов: `CHANGED_FILES_DIAGRAMMY_V625.txt`
- Патч к базе (unified diff): `patches/DiagrammyV625Charts.patch`

Патч рассчитан на применение в корне проекта (пути в стиле `a/...` и `b/...`).

---

## Ограничения и важные замечания

- «Нулевая позиция» реализована как **display‑only трансформация** для графиков/анимации. Физическая корректность базовой позы (ровная дорога, статическое положение, mid‑stroke) должна задаваться начальными условиями/базовым расчётом — UI теперь помогает это **быстро увидеть**.
- `Lock Y by unit` объединяет шкалы **только внутри одной размерности** (например, все mm‑сигналы). Разные физические величины (bar vs mm) не объединяются.

---

## Что дальше (следующие шаги)

1) Явный **Static Baseline Report** (таблица/карточка): штоки в % хода, высоты, углы, предупреждения.
2) Интерактивная связка heatmap → выбор сигналов/прогонов (клик по heatmap).
3) Сохранение/загрузка «профилей сравнения» (набор сигналов, режимы, шкалы).
4) Расширение метаданных `.npz`: сохранять ключевые входные параметры, чтобы строить полноценное N→N влияние (params → metrics).
