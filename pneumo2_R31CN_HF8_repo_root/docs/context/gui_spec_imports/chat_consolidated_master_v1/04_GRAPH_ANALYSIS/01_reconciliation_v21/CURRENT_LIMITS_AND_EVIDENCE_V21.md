# V21: честные границы current evidence

## Что current-layer знает честно
- есть heavy/home поверхность;
- есть отдельная страница оптимизации;
- есть сетка launchpoint-окон;
- есть явные launchpoints: Diagnostics, Send, Compare, Input editor, Test center, Animator, Mnemo, Tools;
- shell всё ещё переходный между web-heavy и canonical desktop-first маршрутом.

## Что current-layer **не знает честно**
Внутренние runtime-композиции следующих окон не были доказаны как полноценно открытые и прочитанные:
- GUI диагностики
- GUI отправки результатов
- Compare Viewer
- Desktop Mnemo
- Редактор исходных данных
- Центр тестов
- Центр desktop-инструментов

Для них в графе допустимы только статусы:
- `launchpoint_only`
- `not_proven_internal`
- `role_reconciled_to_canonical_target`

## Почему это важно
Иначе current-graph начинает притворяться, будто знает внутренний UX окон, которые фактически не были подтверждены live-evidence.
Это ломает честный графовый анализ и делает оптимизацию маршрута недостоверной.

## Что target-layer разрешено делать
Canonical target-layer может:
- задавать прямое открытие из дерева;
- определять first-class/secondary роли окон;
- переносить `GUI отправки результатов` внутрь Diagnostics;
- переносить Compare Viewer в advanced-ветку анализа;
- усиливать роль Редактора кольца как единственного источника сценариев.
