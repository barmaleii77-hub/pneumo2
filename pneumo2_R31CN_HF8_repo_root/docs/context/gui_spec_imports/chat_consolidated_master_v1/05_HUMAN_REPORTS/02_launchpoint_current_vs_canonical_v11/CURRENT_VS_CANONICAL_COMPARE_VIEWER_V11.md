# Compare Viewer — current vs canonical pass

## Current, что честно подтверждено
- Есть отдельная точка входа `Compare Viewer`.
- Есть встроенный compare на основной heavy surface.
- Внутренний layout отдельного окна current живо не раскрыт; статус: `launchpoint_only`.

## Что пользователь понимает сейчас плохо
- Зачем два compare-пути.
- Чем отдельный viewer лучше встроенного compare.
- Что именно сравнивается: текущий vs исторический или исторический vs исторический.
- Совместимы ли два артефакта по contract / baseline / suite / scenario lineage.

## Canonical role
- Отдельное специализированное окно, но не основной compare-route.
- Основной compare-route должен жить в `Анализ результатов` как быстрое сравнение.
- `Compare Viewer` — это `Подробное сравнение результатов`, direct-open advanced route из дерева и из поиска команд.

## Каким должен быть первый экран
1. Контекст сравнения:
   - левый артефакт
   - правый артефакт
   - current/historical
   - contract match / mismatch
2. Режимы просмотра:
   - Overlay
   - Side-by-side
   - Delta
3. Summary различий:
   - ключевые метрики
   - mismatch banner
   - provenance
4. Поясняющий блок:
   - почему compare допустим/недопустим
   - что именно не совпало

## Что исправлять в семантике
- `Compare Viewer` → `Подробное сравнение результатов`
- `Compare` на основном экране → `Быстрое сравнение`
- `Mismatch` → `Несовпадение контракта`
- `Current / Historical` → `Текущий / Исторический`

## Dock/window contract
- отдельное окно допускается;
- direct-open node в левом дереве внутри ветки `Анализ результатов`;
- правый dock: contract/provenance/help;
- нижний dock: summary и delta metrics;
- не скрывать за промежуточным “Desktop tools center”.
