# V19: внутренние action→feedback subgraph-ы

## Что делает V19

V19 перестраивает критичные рабочие пространства не как список экранов, а как внутренние action→feedback графы по четырём зонам: `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION`, `WS-DIAGNOSTICS`. В каждом подграфе отдельно описаны задачи пользователя, проверки, блокировки, возвраты, циклы, сообщения и обязательная когнитивная обратная связь.

## Что нового по сравнению с V18

- V18 держал shell, tree direct-open, cognitive visibility и маршрут верхнего уровня.
- V19 опускается внутрь критичных рабочих пространств и доводит их до операционной понятности: не только куда пользователь заходит, но и что именно он делает, что система проверяет и что человек должен увидеть в ответ.

## Принципы V19

1. Узлы — это не только окна и экраны, но и задачи, checks, blocks, feedback, loops.
2. В оптимизированном слое все значимые элементы и поля из canonical каталогов включены в граф как реальные nodes containment-layer.
3. Current-layer остаётся evidence-bound и не притворяется, что знает внутренности неоткрытых live окон.
4. Прямое открытие из дерева, dock-панели и когнитивная видимость включены в каждый подграф, а не остаются отдельным shell-приложением.

## Масштаб

- Узлы current-layer: 26

- Узлы optimized-layer: 776

- Элементы интерфейса и поля, включённые в optimized-layer: 541

- Семантически разобранных надписей: 812

## Главные current-defects как графовые проблемы

- Входы в Inputs/Ring/Diagnostics по current evidence всё ещё недостаточно доминируют как последовательный маршрут.
- В Inputs пользователь может менять числа раньше, чем увидит, что реально выбраны две пружины, включено выравнивание и заблокирована симметрия.
- В Ring шов, auto-close и семантика сегмента выражены слабее, чем требуют правила.
- В Optimization пользователь всё ещё рискует потеряться между mode selection, contract review, underfill и history.
- В Diagnostics сборка и отправка без явной иерархии создают ложную конкуренцию маршрутов.

## Что оптимизировано

- `WS-INPUTS`: обязательная видимость C1/C2, режима выравнивания, метода и остатка, режима зеркальной симметрии, графических двойников и validated snapshot.

- `WS-RING`: явная геометрическая семантика сегмента, explicit turn type, единственный параметр crossfall, явный seam gate, auto-close последнего сегмента и stale export state.

- `WS-OPTIMIZATION`: один активный mode, contract summary, stage live rows, underfill/gate reasons, promotion reasons, objective-contract в history.

- `WS-DIAGNOSTICS`: один доминирующий collect-route, selfcheck/runtime provenance на первом экране, contents preview до сборки, send только после готового bundle.

## Где смотреть

- `SUBGRAPH_CURRENT_*_V19.dot` — current evidence-bound подграфы.

- `SUBGRAPH_OPTIMIZED_*_V19.dot` — полные canonical action→feedback subgraph-ы.

- `USER_ACTION_FEEDBACK_MATRIX_V19.csv` — все операционные переходы.

- `TASK_CHECK_BLOCK_LOOP_MATRIX_V19.csv` — внутренние рабочие состояния.

- `GUI_LABEL_SEMANTIC_AUDIT_V19.csv` — переписывание надписей и сообщений.

- `COGNITIVE_VISIBILITY_MATRIX_V19.csv` — что пользователь обязан увидеть глазами.

- `TREE_DIRECT_OPEN_MATRIX_V19.csv` — прямое открытие из дерева без промежуточных шагов.

- `DOCK_WINDOW_AND_DOCK_WIDGET_MATRIX_V19.csv` — обязательные dock-элементы и роли.

- `PATH_COST_SCENARIOS_V19.csv` — стоимость внутренних сценариев.

## Честная граница

V19 не выдаёт за доказанное то, что в current runtime не было честно раскрыто. Для `WS-INPUTS`, `WS-RING` и `WS-DIAGNOSTICS` current-internals остаются evidence-bound. Полная coverage-паутина дана только в optimized canonical layer.
