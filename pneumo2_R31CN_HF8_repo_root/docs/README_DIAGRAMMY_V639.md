# Diagrammy + base v6.39 — пакет диаграмм/сравнения (Web + Windows GUI)

Этот релиз — интеграционный слой «Диаграммы» поверх **UnifiedPneumoApp_UNIFIED_v6_39_WINSAFE**.

Цель: дать **максимально информативные сравнительные диаграммы** для анализа результатов симуляций (включая анализ типа **N параметров → N метрик/сигналов**), с **быстрой навигацией**, одинаковой логикой в **Web** и **Windows GUI**, и с упором на **GUI**.

## Главное, что сделано

### 1) Единое «ядро» сравнения (чтобы Web и GUI не расходились)
Файл: `pneumo_solver_ui/compare_ui.py`

- Унифицирована загрузка NPZ (`load_npz_bundle`) и извлечение таблиц (main/p/q/open/full).
- Приведение единиц и режимов:
  - расстояния: m↔mm
  - углы: rad↔deg
  - давление: absolute↔gauge (относительно атмосферного)
  - расходы: поддержан режим отображения в **Nl/min (ANR)** для массовых расходов (если в названии сигнала распознаётся kg/s).
- «Нулевая поза» (baseline/zero):
  - `t0`, `median_window`, `mean_window`, `median_first_n`, `mean_first_n`
  - по умолчанию рассчитано на вашу постановку: **ровная дорога = 0**, статическая подвеска, и дальше отклонения считаются относительно статического положения.
- Δ‑анализ:
  - матрица `max|Δ|` по сигналам×прогонам
  - матрица `Δ(t)` сигнал×время (с опциями `abs` и `normalize_by_range`)
- «Одинаковые шкалы»:
  - лок шкал по сигналу и/или по единице измерения
  - robust‑диапазон (квантили) и симметрия вокруг 0 (для Δ)
- Хелперы для «безопасных подписей»:
  - `shorten_label()` — сокращает длинные имена
  - `sparse_ticks()` — разрежает подписи категориальных осей

### 2) Web‑сравнение (Streamlit) стало тонкой обёрткой над модулем
Файл: `pneumo_solver_ui/pages/06_CompareNPZ_Web.py`

Теперь страница **не дублирует** логику — всё в `pneumo_solver_ui/compare_npz_web.py`. Это уменьшает риск расхождения функциональности.

### 3) Compare NPZ (Web): больше типов диаграмм + контроль читаемости
Файл: `pneumo_solver_ui/compare_npz_web.py`

Добавлены и объединены в один workflow:

- **Overlay / Δ** по выбранным сигналам (малые мультиплоты / small multiples).
- **max|Δ| heatmap** (с разреженными подписями и full‑name в hover).
- **Δ(t) heatmap** (signal×time) — быстро показывает, где именно «разъехались» кривые.
- **Correlation heatmap** для метрик/параметров.
- Дополнительные типы диаграмм (для быстрой диагностики и анализа «формы»):
  - Scatter
  - Histogram / ECDF
  - Density contour
  - Parallel coordinates
  - Radar (spider)
  - Scatter matrix
  - PSD (Welch)
  - Phase plot (y1 vs y2)

#### Анти‑наложение подписей (важно!)
Чтобы **подписи не налезали**:
- единый helper `_apply_safe_plotly_layout()`:
  - увеличенные margin’ы (динамически по длине подписей)
  - `automargin=True` для осей
  - `uniformtext_mode="hide"` для текстов
- для категориальных осей: `_apply_sparse_cat_ticks()`
- длинные имена укорачиваются на осях/легенде, а **полные имена доступны в hover**.

### 4) Windows GUI viewer: функциональный паритет с Web (и удобнее навигация)
Файл: `pneumo_solver_ui/qt_compare_viewer.py`

GUI viewer поддерживает:
- выбор runs / table / signals
- overlay и Δ
- playhead (синхронизация по времени)
- lock шкал (signal / unit / global)
- heatmap max|Δ| и Δ(t)
- **экспорт/импорт CompareSession JSON** (чтобы один раз настроить в Web и открыть в GUI, или наоборот)

#### Анти‑наложение подписей в GUI
- `AxisItem.setStyle(autoExpandTextSpace=True)`
- уменьшенный шрифт тик‑меток
- сокращение длинных имен + вывод полной информации в tooltip/side‑панели

### 5) Встроенные автономные самопроверки (регрессии ловим автоматически)
- `pneumo_solver_ui/self_check_diagrammy.py` — быстрый автономный self-check «диаграммного» слоя.
- `pneumo_solver_ui/self_check.py` теперь запускает Diagrammy self-check как шаг `[11]`.

Это даёт автоматическую гарантию, что:
- API compare_ui не «разъехался»
- baseline/Δ/lock ranges работают
- PSD/ресэмплинг не сломаны

## Как запустить

### Web (Streamlit)
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
Далее откройте страницу: **Compare NPZ (Web)**.

### Windows GUI (Qt viewer)
```bash
python pneumo_solver_ui/qt_compare_viewer.py path1.npz path2.npz
```
или (если PYTHONPATH настроен):
```bash
python -m pneumo_solver_ui.qt_compare_viewer path1.npz path2.npz
```

### Сессии (Web ↔ GUI)
- В Web: скачайте `CompareSession.json`
- В GUI: `File → Load Session` и получите те же выбранные сигналы/режимы/настройки

### Самопроверки
```bash
python pneumo_solver_ui/self_check.py
python pneumo_solver_ui/self_check_diagrammy.py
```

## Где что лежит

- `pneumo_solver_ui/compare_ui.py` — ядро: units, baseline, Δ, lock ranges.
- `pneumo_solver_ui/compare_npz_web.py` — Web интерфейс сравнительных диаграмм.
- `pneumo_solver_ui/qt_compare_viewer.py` — Windows GUI viewer.
- `pneumo_solver_ui/compare_session.py` — формат CompareSession JSON.
- `pneumo_solver_ui/influence_tools.py` — метрики/матрицы корреляции (N→N анализ).

## Диффы и патчи

- `CHANGED_FILES_DIAGRAMMY_V639.txt` — список изменённых/добавленных файлов.
- `diffs/DiagrammyV639_diff.txt` — машинный список отличий.
- `patches/DiagrammyV639.patch` — единый patch (base v6.39 → этот пакет).

## Примечания по “нулевой позе”

В большинстве графиков включено **zero_baseline**. Рекомендуемый режим для вашей постановки:
- `baseline_mode = t0`, если первый момент времени — статическая подвеска на ровной дороге.
- если в начале есть переходный процесс/шум — используйте `median_window` и задайте окно (например 0.1–0.3 s).

---

DiagrammyV639 — интеграционный релиз: привёл в порядок и расширил сравнение результатов так, чтобы **и Web, и GUI** имели **одинаковую логику**, а диаграммы были **информативными и читаемыми**.
