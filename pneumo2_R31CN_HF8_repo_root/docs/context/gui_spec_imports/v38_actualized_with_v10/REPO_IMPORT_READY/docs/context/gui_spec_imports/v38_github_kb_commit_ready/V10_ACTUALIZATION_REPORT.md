# V38 actualization with V10 launcher-shell findings

Этот пакет является **актуализацией V38** на основании проверенного report-only слоя **V10 launcher-shell hierarchy**.

Что именно было встроено:
- в спецификацию добавлен явный **dominant start route** из 8 шагов;
- закреплено, что `Редактор кольца` должен читаться как **доминирующий сценарный центр**;
- зафиксировано, что `GUI отправки результатов` — **не отдельный стартовый путь**, а вложенное действие после готового diagnostics bundle;
- закреплено, что встроенное сравнение в `WS-ANALYSIS` является **основным compare-route**, а `Compare Viewer` — расширенный режим;
- закреплено, что `Desktop Mnemo` и `Инструменты` являются **advanced / secondary** launcher-surfaces, а не равноправными первыми шагами.

Что **не** менялось:
- продуктовый канон `17/18` остаётся выше imported layer;
- пакет не объявляет runtime closure proof;
- producer-side truth, measured browser perf trace и Windows visual acceptance остаются открытыми до отдельного evidence-layer.
