# V21: evidence-bound current ⇄ canonical target reconciliation pass

## Что делает V21

V21 не строит ещё один общий граф поверх всего проекта.
Он делает следующий логичный слой после V20:

1. берёт **current evidence-bound GUI**;
2. отделяет то, что реально подтверждено, от того, что подтверждено только как launchpoint;
3. сводит это с **canonical target GUI**;
4. фиксирует, какие окна/workspace должны остаться top-level, какие должны стать secondary, а какие должны уйти внутрь других поверхностей;
5. оптимизирует маршрут пользователя **как граф ролей и правил открытия**, а не как набор кнопок.

## Главный вывод

Сейчас главный графовый конфликт находится не внутри отдельных расчётных экранов, а на уровне **launcher-shell**:

- early branching начинается слишком рано;
- current shell даёт пользователю слишком много почти равноправных входов;
- `GUI диагностики` и `GUI отправки результатов` формируют ложную развилку;
- `Compare Viewer` спорит со встроенным compare за primary route;
- `Редактор кольца` по канону должен доминировать сильнее, чем это видно в current start route.

## Что V21 признаёт честно

Current-layer не притворяется, что знает внутренности окон, которые были подтверждены только как launchpoints.
Поэтому reconciliation идёт в два шага:

- **current evidence**
- **canonical target role**

Это принципиально лучше, чем подменять live-evidence фантазией.

## Основные решения reconciliation

### 1. Главная heavy/home поверхность
Остаётся стартовой оболочкой только как обзор и next-action surface.
Она не должна оставаться каталогом равноправных инженерных входов.

### 2. Оптимизация
Shell должен иметь **один** маршрут к `WS-OPTIMIZATION`.
Home-summary может показывать статус, но не должен спорить с инженерной страницей за primary route.

### 3. Диагностика
`GUI диагностики` становится единственным first-class diagnostics-route.
`GUI отправки результатов` перестаёт быть отдельным стартовым маршрутом и становится вторичным действием внутри Diagnostics.

### 4. Compare
Встроенное сравнение внутри анализа остаётся primary compare route.
`Compare Viewer` остаётся top-level специализированным окном, но только как advanced route.

### 5. Ring
`Редактор кольца` усиливается как второй шаг основной цепочки и как единственный сценарный source-of-truth.

### 6. Tools / Mnemo
`Desktop Mnemo` и `Инструменты` не пропадают, но понижаются в shell hierarchy:
они не должны перегружать стартовую сетку почти равноправными кнопками.

## Масштаб пакета

- reconciled current surfaces: 12
- launchpoint-only windows triaged: 7
- direct-open targets formalized: 12
- semantic rewrites prepared: 24
- route cost rebalance scenarios: 6

## Где смотреть сначала
1. `CURRENT_TO_CANONICAL_RECONCILIATION_V21.csv`
2. `CURRENT_TARGET_DELTA_GRAPH_V21.dot`
3. `DIRECT_TREE_OPEN_ENFORCEMENT_V21.csv`
4. `SEMANTIC_REWRITE_PLAN_V21.csv`
5. `CURRENT_LIMITS_AND_EVIDENCE_V21.md`
