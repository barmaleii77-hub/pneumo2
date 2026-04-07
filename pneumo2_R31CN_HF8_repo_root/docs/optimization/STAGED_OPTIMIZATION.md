# Staged optimization (StageRunner)

Файл: `pneumo_solver_ui/opt_stage_runner_v1.py`

## Идея

Оптимизация сложной многопараметрической модели на «дорогих» тестах (длинные профили дороги, множество сценариев, мелкий dt) редко должна начинаться сразу с полного бюджета.

Здесь используется **многостадийная** схема:
1) **Stage0 (relevance / cheap)** — быстро отсеять нерелевантные области параметров и проверить, что матмодель реагирует адекватно.
2) **Stage1 (long)** — добавить длительные тесты и часть сценариев.
3) **Stage2 (final)** — полный набор тестов + расширенная матрица сценариев.

При этом:
- размерность пространства параметров растёт по стадиям (**influence-based parameter staging**)
- используется **резюмирование** (повторный запуск продолжает писать в те же файлы)
- используется **глобальный архив** для warm-start (mu/cov для CEM)
- найденный лучший результат обновляет **baseline**.

## Objective contract

Начиная с HF7 StageRunner использует **тот же explicit objective stack**, что и distributed coordinator:
- penalty / feasibility key идёт первым как hard gate;
- затем лексикографически идут objective keys в том порядке, который передал UI/CLI;
- по умолчанию это canonical stack `comfort -> roll -> energy`;
- если пользователь вручную поменял objective keys, StageRunner применяет именно их к promotion, warm-start и baseline update, а не тихо возвращается к legacy `stability/comfort/energy`.

## Как StageRunner решает задачу

### 1) Influence-based parameter staging
В начале прогоняется:
- `pneumo_solver_ui/calibration/system_influence_report_v1.py`
- затем `pneumo_solver_ui/calibration/param_staging_v3_influence.py`

На выходе в `run_dir/staging/` формируются `fit_ranges_stage_XX.json`.

StageRunner выбирает:
- `stage0`: первый файл (минимальный активный набор)
- `stage1`: второй файл
- `stage2`: последний файл (полный набор)

### 2) Тесты по стадиям
В suite добавлен столбец `стадия`.

Фильтр:
- stage0: тесты со `стадия <= 0`
- stage1: `<= 1`
- stage2: `<= 2`

Если `стадия` не заполнена, применяется эвристика:
- `инерция_*`, `микро_*`, `комбо_*` => 0
- тесты с `road_surface` или `road_csv` => 1

### 3) Fidelity scaling
StageRunner масштабирует:
- `dt *= dt_scale`
- `t_end *= t_end_scale`

По умолчанию:
- stage0: dt_scale=2.0, t_end_scale=0.4
- stage1: dt_scale=1.2, t_end_scale=1.0
- stage2: dt_scale=1.0, t_end_scale=1.0

### 4) Матрица сценариев
Для устойчивости решений используется матрица внешних условий.

Реализация:
- Каждый тест размножается на набор сценариев
- В имени появляется суффикс `__sc_<id>`
- В тест добавляется `params_override` (словарь), который применится **только для этого теста**.

Дефолтные сценарии (см. код StageRunner):
- `nominal` — базовый
- `heavy` — +масса
- `hot` — повышенная температура воздуха
- `cold` — пониженная температура воздуха
- `lowP_init` — сниженное начальное давление аккумулятора

## Резюмирование

StageRunner считается резюмируемым если:
- папка `run_dir` существует
- внутри есть stage-папки и csv

Повторный запуск:
- пропускает стадии, у которых есть `DONE.txt`
- для незавершённых стадий заново запускает worker с теми же путями — worker сам резюмирует по CSV.

## Прогресс
StageRunner пишет прогресс в JSON (передаётся из UI):
- текущая стадия
- прогресс worker-а (подхватывается из `<stage_out>.csv_progress.json`)
- лучший найденный кандидат

