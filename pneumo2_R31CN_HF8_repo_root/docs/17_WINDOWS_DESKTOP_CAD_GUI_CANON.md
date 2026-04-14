# Windows Desktop CAD GUI Canon

Этот документ задаёт project-wide baseline для desktop GUI в `pneumo2`. Он трактует классический Microsoft Win32 UX Guide как источник legacy-принципов, которые нужно сверять с current Windows guidance по accessibility, navigation, controls, input и DPI, а не копировать буквально. Канон обязателен для shell, editor-окон, viewport/workspace-поверхностей и analysis-модулей. Утилитарные окна могут отходить от CAD-layout, если у них нет document/viewport surface, но обязаны сохранять keyboard-first, accessibility, DPI и performance discipline.

## 1. Информационная архитектура

- Проект проектируется как native Windows desktop engineering software, а не как web-страница в окне.
- Главное окно должно сохранять нативные ожидания Windows: стандартную строку заголовка, system menu, перетаскивание окна, двойной щелчок для разворачивания, правый щелчок по заголовку и совместимость с Snap Layouts.
- Базовая топология desktop suite: shell, специализированные рабочие центры, отдельные специализированные окна и вспомогательные утилиты.
- Главный смысл интерфейса там, где это уместно, должен строиться вокруг document/viewport-first surface.
- Служебные элементы, диагностика, редкие команды и технические детали уводятся на второй и третий план, а не конкурируют с рабочей областью.
- Слева browser/tree допускается только там, где реально есть иерархия: assembly tree, feature tree, scenario tree, object graph, study tree, project structure.
- Справа основной secondary surface это context-sensitive properties/inspector pane для текущего объекта, команды или режима.
- Для широких справочных наборов данных использовать list/details или master/detail, а не гигантские сетки с постоянным горизонтальным скроллом.
- Все пользовательские величины подписываются названием и единицей измерения: `Давление, МПа`, `Скорость, м/с`, `Ход штока, мм`. Обозначения без названий запрещены.

## 2. Layout главного окна с перечнем panes

- Верх окна: `menu bar`, под ним `toolbar` или command strip с самыми частыми действиями.
- Если title bar кастомизируется, нельзя ломать стандартные Windows-affordances: drag, maximize, system menu, snap и resize behavior.
- Под командной поверхностью должен быть доступен единый `command search`, который не прячет core-команды за hamburger или web-style navigation.
- Центральная область: document well, modeling or analysis viewport, drawing canvas, preview surface или другая главная рабочая поверхность.
- Левая панель: browser/tree, project navigator или scenario list только при наличии реальной иерархии; панель должна быть dockable, resizable и при необходимости auto-hide.
- Правая панель: context-sensitive inspector/properties pane; она должна быть resizable, dockable, detachable и пригодной для второго монитора.
- Нижняя полоса: status/progress strip для состояния режима, координат, выделения, background task progress, solver state и других полезных, но не критичных сигналов.
- Вокруг document area допускаются дополнительные panes: selection filters, layers, diagnostics, job queue, results summary, reference snippets, если они не съедают рабочую площадь без пользы.
- Везде, где уместно, должны быть явные scrollbars и resize affordances. Плавающие и docked panes должны визуально показывать, что их можно менять по размеру и положению.
- Раскладки docked, floating и auto-hide panes должны сохраняться и восстанавливаться между сеансами как baseline desktop behavior.
- Docking policy допускается описывать machine-readable matrix-слоем: какие pane можно dock/float/auto-hide/выносить на второй монитор, а какие являются document-centered surface и не должны терять основной anchor.
- Для 3D surfaces обязателен orientation widget уровня `ViewCube`: стандартные виды, возврат к orientation presets, настраиваемые размер и положение, без засорения viewport.

## 3. Command model: menu, toolbar, palettes, context menu, search

- Project-wide baseline command surface: `menu bar + toolbar + dockable/floating/auto-hide panes + command search + status/progress strip`.
- `Ribbon` не является baseline-режимом по умолчанию. Он допустим только как отдельно обоснованное исключение для конкретного workspace, если это реально улучшает discoverability при большом наборе команд.
- Даже если где-то появляется `Ribbon`, он не должен быть слепым переносом menus/toolbars и не должен становиться обязательным шаблоном для всех окон проекта.
- `Home`-уровень команд должен содержать самые частые действия. Редкие и опасные команды не должны конкурировать с повседневными.
- `Context menu` обязателен для selection-oriented действий, но не должен быть единственным способом дойти до core-функции.
- `Command search` обязателен. Он должен искать по partial match, запускать команду сразу, показывать путь до команды в UI, терпеть частичные и неточные вводы, ранжировать по частоте и по возможности поддерживать synonyms из других CAD-систем.
- Palette windows и tool windows допустимы как first-class command surfaces для repeated workflows, особенно когда важны кастомизация, второй монитор и сохранение layout.
- Для объектов и режимов использовать contextual commands, но не превращать интерфейс в нестабильный набор внезапно исчезающих controls.
- Tooltip, краткая встроенная help и shortcut hints должны дополнять command architecture, но не заменять понятную информационную архитектуру и видимые core-команды.

## 4. Сценарии работы: selection, editing, view navigation, analysis, export

- `Selection`: пользователь должен быстро выбрать объект из viewport, tree, списка или search; selection state должен сразу отражаться в inspector pane и status strip.
- `Editing`: частые правки выполнять через modeless panes и inspector с immediate commit, а не через цепочки модальных окон.
- `View navigation`: pan, zoom, fit, standard views, isolate, show/hide overlays и related navigation commands должны быть доступны мышью, клавиатурой и из командной поверхности.
- `Analysis`: инженерные результаты, previews, reference overlays, warnings и solver diagnostics должны жить рядом с рабочей поверхностью и не ломать основной поток работы.
- `Export`: экспорт, запуск расчёта, сбор артефактов и handoff-действия должны быть discoverable и не зависеть только от статуса внизу окна.
- Для geometry-, ring-, animation- и analysis-workflows viewport или preview должны оставаться главным объектом внимания, а не превращаться в вторичную вкладку после формы.
- Если окно показывает 3D viewport, navigation model должна включать orientation widget, standard views, predictable camera reset и понятное переключение между orthographic и perspective режимами.
- При progressive disclosure скрытые блоки должны выглядеть явно expandable/collapsible, а состояние раскрытия должно быть предсказуемым и обратимым.

## 5. Dialog/panel policy: modal, modeless, wizard, inline

- `Modeless` panes и dockable tool windows использовать для частых повторяющихся действий и ongoing workflows. Здесь базовое правило: immediate commit.
- `Modal dialogs` использовать для редких, опасных или decision-gated действий, где пользователь должен закончить выбор до продолжения. Здесь базовое правило: delayed commit.
- `Wizards` применять только для действительно multi-step процессов с явной последовательностью и риском ошибки. Если задачу можно решить inline или через properties pane, выбирать более лёгкий вариант.
- `Inline` editing допустим для частых локальных правок в списках, таблицах, browser-узлах и cards, если это не ухудшает понятность и не ломает validation.
- `Apply` использовать только там, где реально есть property-sheet semantics.
- Scrollable dialogs запрещены как baseline pattern. Если диалог разрастается, его нужно делить на tabs, sections или переносить часть настроек в modeless pane.
- Menu bar и status bar не встраивать внутрь обычных dialogs.
- Для file open/save/print/font/color использовать стандартные Windows common dialogs.
- В modeless dialogs и panes закрытие обозначать как `Close`, а не как `Cancel`, если отмены изменений уже нет.

## 6. Keyboard map и accessibility policy

- Keyboard-first работа обязательна: логичный tab order, `F6` и `Shift+F6` между major regions, `Arrow keys` внутри composite controls, `Esc` для понятного выхода из режимов и `Enter` там, где он ожидаем.
- Сохранять стандартные Windows shortcuts и vocabulary: `Ctrl+Z`, `Ctrl+Y`, `Ctrl+C`, `Ctrl+V`, `Ctrl+F`, `F1`, `Ctrl+P` и другие общеожидаемые сочетания.
- Частые команды должны иметь shortcuts; важные controls должны иметь access keys; tooltip и help metadata должны раскрывать shortcut hints.
- Keyboard map может быть отдельным contract artifact, если он явно фиксирует `F6`-порядок регионов, search shortcut, primary action shortcut и access-key discipline.
- Screen reader support и `UI Automation` exposure обязательны для всех важных элементов, включая custom controls.
- Для элементов должны быть корректные accessible names, roles, values, states и focus indicators.
- Контраст текста не ниже `4.5:1`. Критичный смысл нельзя передавать только цветом, особенно только красным и зелёным.
- Поддерживать contrast themes и проверять работу в high-contrast режимах Windows.
- Accessibility проверять рано и регулярно с screen reader, `Inspect` и профильными accessibility tools, а не откладывать на финальный полировочный этап.

## 7. High-DPI, theming и performance checklist

- Проектировать как `Per-Monitor DPI aware`, предпочтительно `PMv2 (Per-Monitor V2)`.
- Blur и bitmap stretch не считаются нормальным режимом. При смене DPI нужно пересчитывать размеры controls, шрифты и bitmap assets.
- Для Win32 path использовать suggested rectangle из `WM_DPICHANGED`; mixed-DPI и multi-monitor сценарии обязательны в тестах.
- Плавающие secondary windows, detached panes и tool windows не должны ломаться при переносе между мониторами с разным DPI.
- Поддерживать `light theme`, `dark theme` и contrast-friendly themes; предпочтение темы пользователя уважать по умолчанию.
- Accent color использовать сдержанно: для важного interactive state, focus, selection и progress, а не для тотальной заливки интерфейса.
- Performance policy должна быть измеримой: launch responsiveness, key interactions, background work, idle CPU, memory usage, power use, state restore и UI latency должны иметь измеряемые сценарии.
- Для длительных операций показывать progress. Determinate progress использовать whenever possible, плюс `Cancel` или `Stop`, когда это безопасно.
- In-window progress обязателен; taskbar progress в Windows допустим только как отражение более подробного индикатора внутри окна, а не как его замена.
- Background work не должен держать UI постоянно “живым” без пользы. Wakeups, polling и лишние redraws нужно минимизировать. Для замеров использовать instrumentation и telemetry уровня ETW-style measurements, где это уместно.

## 8. Anti-patterns, компромиссы и сжатая формула

- Запрещено делать `Ribbon` только “потому что солидно”. Если он уменьшает полезную площадь viewport или заставляет пользователя бесконечно переключать tabs, это неверное решение.
- Запрещено прятать критичную информацию только в status bar.
- Запрещено ломать нативное Windows-поведение окна ради кастомной chrome или декоративного title bar.
- Запрещены noisy notifications, dialog sprawl, mouse-only core flows, скрытые advanced options без явной disclosure affordance и scrollable dialogs.
- Запрещён web-app minimalism, который режет discoverability профессиональных команд, рабочих panes и keyboard-first сценариев.
- Компромисс допустим между плотностью команд и площадью viewport, но по умолчанию выигрывает рабочая эффективность инженера, а не декоративная чистота экрана.
- Компромисс допустим между единым baseline и спецификой отдельных окон: specialized tools могут отходить от общего CAD-layout, если они сохраняют project-wide command discipline, accessibility, DPI и performance policy.
- Любое отклонение от этого канона должно быть локально обосновано в prompt, spec или design note для конкретного workspace.
- Сжатая формула: большой центральный viewport или document area, вокруг него dockable workflow panes, сверху понятная command surface, справа context-sensitive properties, слева иерархия только по делу, снизу status/progress strip, везде keyboard-first accessibility, честный High-DPI и измеримая отзывчивость.

## 9. Explainability, help-pane и provenance contract

- Каждый значимый control обязан иметь короткий tooltip и отдельную modeless-affordance `?`, открывающую расширенную помощь в inspector/help pane, а не в новом модальном окне, если нет жёсткой причины для modal flow.
- `Command search` индексирует не только названия команд, но и help-tags, tooltip-теги, проектные сущности, артефакты и миграционные синонимы из старых web-маршрутов.
- Результат `command search` показывает не только имя команды, но и путь к ней: workspace, docked pane, отдельное окно или специализированный инструмент.
- Любой расчётный preview, overlay, график и анимационная поверхность обязаны показывать `источник представления` и `время построения`; для cached/exported artifacts дополнительно показываются run id, путь к артефакту или эквивалентный provenance marker.
- Help metadata, provenance markers и warning states должны быть доступны не только мышью, но и с клавиатуры, через inspector pane, accessible names, adjacent descriptive text и другие UI Automation-friendly surfaces.
- Idle-поведение является частью GUI contract: hidden panes, detached windows и неактивные surfaces обязаны останавливать timers, polling и ненужные redraw loops, а instrumentation уровня ETW-style or equivalent telemetry должно уметь отличать visible work, hidden work и idle wakeups.

## 10. Element Registries And Verification Hooks

- Для desktop GUI допустим machine-readable contract layer с координатами, прямоугольниками и ownership регионов окна, если он не подменяет human-readable canon и используется как reference artifact.
- Каждый интерактивный элемент обязан иметь стабильный `automation_id`, пригодный для UI Automation, smoke tests, acceptance checks и replayable diagnostics.
- Для каждого meaningful interactive element обязательны `tooltip + help` linkage, а для keyboard-first сценариев также access key, hotkey и понятный tab order.
- Layout и shell-regions могут описываться машиночитаемо на базовом окне наподобие `1920x1080`, но реализация обязана оставаться DPI-aware и не трактовать pixel coordinates как жёсткую отрисовочную геометрию на любом мониторе.
- Source-of-truth matrix допустима как contract artifact: она должна явно разводить master-copy данных и производные представления, а также запрещённые дублирующие места редактирования.
- UI state matrix допустима как verification-layer для `default/hover/focus/dirty/valid/warning/error`, если она не подменяет accessibility semantics и не сводит смысл состояния только к цвету.
- Observability hooks для GUI pipeline допустимо хранить как machine-readable event catalog с обязательными полями payload, если этот слой поддерживает acceptance/performance и regression verification, а не заменяет UX-канон.
- Acceptance, performance и pipeline verification допустимо хранить отдельными machine-readable suites, если human-readable docs явно говорят, что это verification layer, а не самостоятельный канон.
- `Command search` должен быть индексируемой surface не только для команд, но и для help topics, field registries, migration aliases, test entities и artifact routes.
