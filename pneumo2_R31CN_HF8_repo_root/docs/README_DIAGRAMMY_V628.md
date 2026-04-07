# Diagrammy — пакет улучшений диаграмм для UnifiedPneumoApp v6.28 (WINSAFE)

База: `UnifiedPneumoApp_UNIFIED_v6_28_WINSAFE` (из вашего ZIP).  
Этот пакет **сохраняет функционал базы** и добавляет/исправляет то, что критично для инженерного сравнения прогонов.

## Что сделано (главное)

### 1) Web: Compare NPZ (overlay/Δ) + одинаковые шкалы + playhead + heatmap + N→N influence
Добавлена страница **Compare NPZ (Web)**:
- Overlay и **Δ к reference** (reference выбирается).
- **Нулевая базовая поза** для перемещений/углов/дороги (display-only): статика=0.
- **Одинаковые шкалы Y** по умолчанию: `Lock Y by unit` (можно отключить).
- Playhead (индекс/время) + вертикальная линия на всех графиках.
- Heatmap: `max |Δ|` по каждому сигналу vs reference.
- Influence (N×N): корреляция **числовых параметров из meta** → **метрики сигналов** (RMS/peak).

Файлы:
- `pneumo_solver_ui/compare_npz_web.py`
- `pneumo_solver_ui/pages/06_CompareNPZ_Web.py`
- `app.py` (включена в навигацию)

### 2) Web: Validation Cockpit (один экран) — анимация + ключевые графики + проверка статики
Добавлена страница **Validation Cockpit (Web)**:
- Выбор одного NPZ.
- **2D/3D анимация** (mech_anim / mech_car3d) с общим playhead.
- Small multiples ключевых сигналов (body/wheel/road/stroke/angles) с нулевой базой.
- Отчёт по **штокам в t0**: процент хода и отклонение от 50% (цель “середина хода”).

Файлы:
- `pneumo_solver_ui/validation_cockpit_web.py`
- `pneumo_solver_ui/pages/08_ValidationCockpit_Web.py`
- `app.py` (включена в навигацию)

### 3) Desktop (Qt): Compare Viewer — улучшена информативность + Δ heatmap
Обновлён desktop viewer:
- Нулевая базовая поза (позиции/углы) + окно baseline.
- Одинаковые шкалы Y (по сигналу / по unit) — **по unit включено по умолчанию**.
- Δ к первому выбранному run.
- Playhead (скраб/Play) уже был — сохранён.
- Добавлена кнопка **Δ Heatmap** (матрица `max|Δ|`).

Файл:
- `pneumo_solver_ui/qt_compare_viewer.py`

### 4) Анимация: “нулевая позиция” и статика в компонентах
- `mech_anim`: крен/тангаж теперь отображаются **относительно t0**, а штоки показываются как `мм + % хода` (цель ~50%).
- `mech_car3d`: добавлен baseline по t0 для кузова/углов и дорога выравнивается в 0 по каждому колесу в t0.

Файлы:
- `pneumo_solver_ui/components/mech_anim/index.html`
- `pneumo_solver_ui/components/mech_car3d/index.html`

### 5) Исправления/интеграция
- Исправлен fallback в `safe_plotly_chart` (корректный `use_container_width`).
- `05_ParamInfluence.py` больше не делает `runpy.run_path` — прямой импорт `render_param_influence_ui()`.

Файлы:
- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/pages/05_ParamInfluence.py`

### 6) Библиотека сравнения (общая логика единиц/нулевой базы/временной сетки)
Усилен `compare_ui.py`:
- корректный bar = 100000 Pa, поддержка gauge/abs
- нулевая база для disp/angle
- общая временная сетка/интерполяция
- robust min/max и lock-ranges по unit
- helper для kg/s → Nl/min (ANR) (display-only)

Файл:
- `pneumo_solver_ui/compare_ui.py` (и shim `compare_ui.py` в корне проекта остаётся совместимым)

## Как запустить

### Web
```bash
python -m pip install -r pneumo_solver_ui/requirements.txt
streamlit run app.py
```
Далее откройте страницы:
- **Compare NPZ (Web)**
- **Validation Cockpit (Web)**

### Desktop (Windows)
```bash
python -m pip install -r pneumo_solver_ui/requirements.txt
python -m pip install -r pneumo_solver_ui/requirements_desktop_compare.txt
python pneumo_solver_ui/qt_compare_viewer.py
```

## Где лежит что
- `pneumo_solver_ui/compare_npz_web.py` — web сравнение прогонов
- `pneumo_solver_ui/validation_cockpit_web.py` — “один экран” валидации
- `pneumo_solver_ui/qt_compare_viewer.py` — Qt viewer (desktop)
- `pneumo_solver_ui/compare_ui.py` — общие утилиты NPZ/units/baseline
- `pneumo_solver_ui/components/*` — фронтенд-компоненты анимации

## Ограничения (честно)
- Блок “статика = середина хода” сейчас **проверяется/подсвечивается** (t0), но не “чинит” солвер. Если нужно, следующий шаг — добавить/интегрировать статический решатель начальных условий (equilibrium) перед динамикой.

