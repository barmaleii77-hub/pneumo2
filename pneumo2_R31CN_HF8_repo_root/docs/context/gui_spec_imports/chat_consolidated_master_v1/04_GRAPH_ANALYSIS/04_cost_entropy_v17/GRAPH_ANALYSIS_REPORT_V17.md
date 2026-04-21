# V17: path-cost optimization pass

## Что делает V17
V17 — это не новая карта экранов, а **cost-overlay** поверх полного graph-layer V16.
Он пересчитывает цену маршрутов пользователя по основным сценариям, особенно для:
- launch-shell;
- diagnostics-route;
- compare-route.

## Модель стоимости
Используется взвешенный directed graph.
Стоимость перехода считается как:

`cost = base_transition + target_interaction + entropy(source) + label_penalty(target) + route_split_penalty + advanced_penalty + unknown_penalty`

### Что означают компоненты
- `base_transition` — цена самого перехода;
- `target_interaction` — цена входа в тип узла;
- `entropy(source)` — цена ветвления и количества альтернатив в точке выбора;
- `label_penalty(target)` — цена двусмысленной, смешанной или внутренней подписи;
- `route_split_penalty` — цена ложного раздвоения маршрута;
- `advanced_penalty` — цена преждевременного ухода в advanced/off-ramp окно;
- `unknown_penalty` — цена окна, внутренности которого не подтверждены живым evidence.

## Главные числа
- current weighted graph: **156 узлов / 255 рёбер**
- optimized weighted graph (полный overlay): **818 узлов / 831 рёбер**
- optimized focus graph: **34 узлов / 39 рёбер**
- semantic rows with cost impact: **900**

## Сценарные результаты
### Launch-shell
- `Исходные данные`: 5.212 → 3.05 (**41.5%**)
- `Редактор кольца`: 5.912 → 3.05 (**48.4%**)
- `Оптимизация`: 5.912 → 3.05 (**48.4%**)

### Diagnostics-route
- current: **6.962**
- optimized: **5.7**
- improvement: **18.1%**

Причина улучшения: диагностика перестаёт спорить с `GUI отправки результатов`; отправка становится вторым действием после готового bundle.

### Compare-route
- current: **7.362**
- optimized: **6.45**
- improvement: **12.4%**

Причина улучшения: embedded compare становится primary route, а `Compare Viewer` переводится в advanced route внутри анализа.

## Главные bottleneck-узлы current graph
1. `SC_HOME` — ранняя энтропия выбора.
2. `HZ_WIN` — плоская сетка launchpoint-окон.
3. `HC_LAUNCH_DIAG` ↔ `HC_LAUNCH_SEND` — ложный diagnostics split.
4. `HC_COMPARE_EMBED` ↔ `HC_LAUNCH_COMPARE` — ложный compare split.
5. `HC_OPEN_MNEMO` и `HC_LAUNCH_TOOLS` — преждевременные advanced off-ramps.

## Что оптимизировано в V17
1. Shell трактуется как **маршрут**, а не каталог.
2. Diagnostics-route получает одну доминирующую entry action.
3. Compare-route разделён на primary quick compare и advanced viewer.
4. Advanced окна уходят во вторую линию.
5. Семантические переписывания считаются не косметикой, а частью path-cost reduction.

## Честная граница
- Current layer по-прежнему не придумывает внутренности окон, которые подтверждены только как launchpoints.
- V17 оптимизирует пути пользователя как граф, но не подменяет producer-side truth для solver/export/animator.
- Focus graph — это path-cost optimized shell overlay поверх полного canonical route layer.
