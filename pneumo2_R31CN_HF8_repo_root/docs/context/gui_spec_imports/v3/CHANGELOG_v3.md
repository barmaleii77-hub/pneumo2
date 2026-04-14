# Changelog v3

## Что дополнено относительно v2
1. Добавлены контракты:
   - источников истины;
   - когнитивной эргономики;
   - состояний элемента;
   - валидации и исправления;
   - undo/redo;
   - пустых и недоступных состояний;
   - таблиц;
   - расширенной клавиатурной карты;
   - наблюдаемости pipeline;
   - окна и title bar;
   - докирования по типам панелей.

2. Дополнены каталоги элементов:
   - title bar;
   - message bar;
   - undo/redo;
   - splitters и scrollbars;
   - empty state для сценариев;
   - баннер расхождения objective contract;
   - stage policy summary;
   - compare picker;
   - playback controls и selection sync;
   - diagnostics bundle contents.

3. Усилен граф pipeline:
   - явные узлы поиска, empty states, contract mismatch, export, diagnostics и undo/redo;
   - больше переходов, у которых определены следующая команда и точка возврата.

4. Усилены acceptance/tests:
   - keyboard-only navigation;
   - empty state correctness;
   - objective-contract mismatch;
   - splitters/scrollbars under snap;
   - degraded animator truth.

## Что не декларируется закрытым
- producer-side truth-contract по hardpoints/solver_points/packaging;
- финальная Windows visual acceptance;
- measured browser performance acceptance;
- полное закрытие cylinder packaging producer truth.
