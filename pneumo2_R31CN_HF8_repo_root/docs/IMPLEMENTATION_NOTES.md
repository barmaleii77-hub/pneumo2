# Implementation notes — Диаграммы V6.32

## 1) Критический фикс: compare_ui.py

В базовой v6.32 присутствовали модули `compare_npz_web.py` и `validation_cockpit_web.py`, которые импортировали функции/константы из `pneumo_solver_ui.compare_ui`, **но базовый compare_ui был урезан** (не содержал `apply_zero_baseline`, `locked_ranges_by_unit`, `BAR_PA`, `P_ATM_DEFAULT`, и т.д.).

Результат: часть страниц Streamlit не могла импортироваться/работать.

В этом релизе:
- `pneumo_solver_ui/compare_ui.py` заменён на расширенную версию (на основе ранее отработанной ветки Diagrammy) + добавлены wrapper-API функции, которые ожидают веб-страницы.
- Добавлены совместимые алиасы (`BAR_PA`, `is_zeroable_unit`, `apply_zero_baseline`, `resample_linear`, `massflow_to_Nl_min_ANR`, `locked_ranges_by_unit`).

## 2) Web Compare NPZ: единый рендерер

Страница `pages/06_CompareNPZ_Web.py` переписана как thin-wrapper, который вызывает `compare_npz_web.render_compare_npz_web()`.

Плюсы:
- один кодовый путь = меньше рассинхронизации Web/GUI,
- все новые фичи (overlay/Δ, locking, heatmaps, influence) в одном месте,
- проще поддерживать.

## 3) Safe Plotly Chart

`pneumo_ui_app.safe_plotly_chart()` был исправлен: корректный fallback на `use_container_width=True` и/или отключение callback-параметров в старых Streamlit.

## 4) Desktop Compare Viewer (Qt)

`pneumo_solver_ui/qt_compare_viewer.py` обновлён до полноценного "Charts Suite" варианта:
- режимы overlay/Δ,
- y-lock: none/signal/unit,
- robust scaling,
- run×signal heatmap (max|Δ|/RMS),
- time×signal heatmap,
- valve timeline (для бинарных/дискретных сигналов),
- playhead + navigator.

