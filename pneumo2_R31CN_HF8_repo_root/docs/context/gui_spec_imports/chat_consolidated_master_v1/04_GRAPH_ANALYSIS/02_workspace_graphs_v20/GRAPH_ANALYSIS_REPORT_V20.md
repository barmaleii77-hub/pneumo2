# V20: action→feedback subgraph pass по оставшимся рабочим пространствам

## Что делает V20

V20 продолжает V19, но добивает **оставшиеся рабочие пространства и межпространственные возвраты**:
- `WS-PROJECT`
- `WS-SUITE`
- `WS-BASELINE`
- `WS-ANALYSIS`
- `WS-ANIMATOR`

Плюс отдельным слоем собран `CROSS_WORKSPACE_RETURN_LOOP_GRAPH_V20`, чтобы граф описывал не только движение вперёд, но и реальные **возвраты, repair-loops и повторные заходы** пользователя.

## Что нового по сравнению с V19

- V19 раскрыл внутренние subgraph-ы `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION`, `WS-DIAGNOSTICS`.
- V20 добивает вторую половину pipeline и делает action→feedback слой **сквозным**.
- В V20 усилен когнитивный слой: пользователь должен не только совершить действие, но и **явно увидеть, что произошло**, особенно для состояний, связанных с видимостью конфигурации, baseline, compare, truth-state и diagnostics route.

## Главные принципы V20

1. Узлы — это задачи, checks, blocks, loops, feedback, controls, fields, messages и workspace roots.
2. Дерево остаётся first-class launcher: открытие рабочего пространства происходит **напрямую из дерева**, без промежуточного «центра окон».
3. Dock-окна и dock-виджеты моделируются как реальные shell-элементы, а не как декоративный слой.
4. Current-layer остаётся evidence-bound и не притворяется, что знает внутренности окон, которые в runtime не были честно раскрыты.
5. Optimized-layer держит canonical target и использует project canon как источник маршрута: Inputs → Ring → Suite → Baseline → Optimization → Analysis → Animator → Diagnostics.

## Масштаб

- current-layer: 43 узлов / 37 рёбер
- optimized-layer: 255 узлов / 277 рёбер
- semantic audit rows: 20
- cross-workspace repair loops: 7

## Что графово улучшено

### 1. Project
Project больше не трактуется как второй редактор параметров. Это входная точка проекта, health summary, last project restore и next action recommender.

### 2. Suite
Suite явно удерживает difference между:
- строкой испытания,
- stage semantics,
- scenario lineage,
- validated snapshot.

### 3. Baseline
Baseline теперь моделируется как отдельный contract-layer:
- выбрать источник,
- выполнить baseline,
- решить политику active baseline,
- передать active baseline дальше.

### 4. Analysis
Analysis получает explicit run-picker, compare contract, mismatch banners и handoff в Animator/Diagnostics.

### 5. Animator
Animator описан как viewport-first workspace с truth-state, playback, overlay-contract и export capture, а не как «ещё одно окно со сценой».

### 6. Cross-workspace loops
Добавлены явные возвраты:
- Suite → Ring
- Baseline → Inputs/Suite
- Analysis → Optimization
- Animator → Analysis
- Diagnostics → Project

## Где смотреть

- `SUBGRAPH_CURRENT_*_V20.dot` — current evidence-bound subgraph-ы
- `SUBGRAPH_OPTIMIZED_*_V20.dot` — full canonical target
- `CROSS_WORKSPACE_RETURN_LOOP_GRAPH_V20.dot` — сквозной граф возвратов и repair-loops
- `COGNITIVE_VISIBILITY_MATRIX_V20.csv` — что пользователь обязан увидеть
- `GUI_LABEL_SEMANTIC_AUDIT_V20.csv` — смысловая очистка надписей
- `PATH_COST_SCENARIOS_V20.csv` — стоимость ключевых сценариев
- `WORKSPACE_CROSS_LOOP_MATRIX_V20.csv` — возвраты между workspace

## Честная граница

V20 не выдаёт за доказанное то, что не подтверждено current runtime-evidence. Для current-layer часть launchpoint-внутренностей по-прежнему честно помечена как `unknown_window_internal`.
