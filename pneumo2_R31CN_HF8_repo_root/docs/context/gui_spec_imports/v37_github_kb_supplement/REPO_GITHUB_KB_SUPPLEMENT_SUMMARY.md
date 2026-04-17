# REPO_GITHUB_KB_SUPPLEMENT_SUMMARY_V37

## Назначение
Этот пакет — **import-ready knowledge-base supplement** для репозитория `pneumo2`.
Он не подменяет `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` и `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`, а
добавляет **consolidated successor layer** в `docs/context/gui_spec_imports/` и готовый patch set для включения этого слоя в активный канон репозитория.

## Что нужно сделать в репозитории
1. Скопировать каталог `REPO_IMPORT_READY/docs/context/gui_spec_imports/v37_github_kb_supplement/`.
2. Применить `PROJECT_SOURCES_PATCH_PROPOSAL.diff`.
3. При желании применить lineage-патчи и индексные дополнения из `PATCHSET/`.
4. Не объявлять пакет runtime-closure proof до закрытия producer-side truth, browser perf trace и Windows visual acceptance.

## Что не меняется
- Приоритет `17 -> 18` остаётся неизменным.
- `v3`, `v13_ring_editor_migration` и `v12_design_recovery` остаются historical/reference layers.
- Открытые runtime gaps не маскируются и не переводятся в `covered` без evidence.

## Почему это соответствует репозиторию
Текущий `docs/PROJECT_SOURCES.md` требует читать сначала `17`, затем `18`, затем imported layers; этот пакет добавляет именно новый imported successor layer, не ломая этот порядок.
