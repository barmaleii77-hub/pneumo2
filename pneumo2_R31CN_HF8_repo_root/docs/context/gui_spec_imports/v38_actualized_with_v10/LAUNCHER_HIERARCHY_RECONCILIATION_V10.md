# Launcher hierarchy reconciliation from V10

## Доминирующий маршрут
Стартовый shell не должен быть каталогом равноправных входов. На первом экране обязан читаться один основной маршрут:

1. Исходные данные
2. Редактор кольца / сценариев
3. Набор испытаний
4. Базовый прогон
5. Оптимизация
6. Анализ результатов
7. Анимация
8. Диагностика

## Launcher priorities
### Primary
- Главное окно shell
- Исходные данные
- Редактор кольца
- Набор испытаний
- Базовый прогон
- Оптимизация
- Анализ результатов
- Диагностика

### Specialized but route-bound
- Desktop Animator

### Advanced / secondary
- Compare Viewer
- Desktop Mnemo
- Инструменты / Desktop Tools Center

## Nested actions
- Отправка результатов — только после готового diagnostics bundle.
- Compare Viewer — только как advanced mode из Analysis.
- Mnemo — только как additional engineering surface из Analysis/Tools.
