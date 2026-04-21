# V16 — policy видимости и приоритет must-see состояний

## 1. Базовое правило
Не все состояния должны быть одинаково видимы.  
Но у каждого workspace есть состояния, которые пользователь обязан увидеть **до** того, как пойдёт в inspector/help, откроет подробный диалог или начнёт искать причину в логах.

## 2. Три уровня видимости

### 2.1. Always visible
Показываются всегда:
- идентичность текущего контекста;
- active source-of-truth;
- активный режим;
- главная задача текущего экрана;
- главный runtime contract, если он влияет на смысл результата.

### 2.2. Conditionally escalated
Показываются только при наличии риска:
- stale;
- dirty;
- mismatch;
- degraded truth;
- blocked action;
- underfill / gate reasons;
- historical/current conflict.

### 2.3. Inspector/help/details
Можно уводить только туда, если:
- это не влияет на первое решение пользователя;
- это не меняет interpretation текущего результата;
- это не является конфликтом;
- это не требуется для repair-route.

## 3. Что нельзя прятать
Нельзя прятать только в inspector/help:
- две пружины на угол;
- выравнивание пружинами, способ и остаток;
- active baseline;
- objective stack;
- hard gate;
- truth-state анимации;
- historical/current mismatch;
- stale diagnostics bundle;
- состояние шва сценария;
- stale link набора испытаний к кольцу.

## 4. Приоритеты по shell
Shell обязан всегда делать видимыми:
- активный проект;
- текущий шаг pipeline;
- одну заметную диагностику;
- глобальный конфликтный banner, если конфликт cross-workspace.

## 5. Приоритеты по workspace
См. матрицы:
- `MUST_SEE_STATE_MATRIX_V16.csv`
- `WORKSPACE_FIRST_5_SECONDS_V16.csv`
- `ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv`

## 6. Dock-правило
Dock-области — это не только layout-решение, но и semantic depth:
- левое дерево = прямой вход и переключение;
- центральная область = primary task и must-see effect;
- правый inspector = свойства, provenance, help, deep details;
- нижняя полоса = ход, playback, фоновый статус;
- message bar = конфликт/repair.

## 7. Repair-first visibility
Если состояние требует repair-loop, пользователь должен видеть:
1. что именно не так;
2. почему это не так;
3. один основной repair-action;
4. куда вернёт после исправления.
