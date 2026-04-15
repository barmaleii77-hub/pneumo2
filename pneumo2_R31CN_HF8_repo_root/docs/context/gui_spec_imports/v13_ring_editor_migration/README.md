# V13 — редактор кольца и миграция web → desktop

Этот пакет продолжает **чистую проектную ветку** после `V12` и не уходит в реализацию.

## Что внутри
- `pneumo_gui_codex_spec_v13_ring_editor_migration.json` — главный машиночитаемый слой для Codex
- `ring_editor_schema_contract_v13.json` — каноническая схема данных кольцевого сценария
- `ring_editor_screen_blueprints_v13.csv` — экраны/режимы рабочего пространства
- `ring_editor_element_catalog_v13.csv` — элементы интерфейса и их размещение
- `ring_editor_field_catalog_v13.csv` — поля, единицы измерения, обязательность и смысл
- `ring_editor_state_machine_v13.json` — состояния редактора кольца
- `ring_editor_user_pipeline_v13.dot` — граф пользовательского потока
- `ring_editor_user_steps_v13.csv` — пошаговое описание user → GUI → user
- `web_to_desktop_migration_matrix_v13.csv` — ring-level матрица переноса без потери функций
- `ring_editor_acceptance_gates_v13.csv` — критерии приёмки сценарного контура
- `ring_to_suite_link_contract_v13.json` — контракт связи WS-RING → WS-SUITE
- `artifact_lineage_v13.json` — место пакета в канонической ветке

## Откуда продолжать дальше
Следующий корректный слой после V13:
**детализация WS-SUITE как consumer кольцевого контракта** и закрытие handoff между
`WS-RING -> WS-SUITE -> WS-BASELINE -> WS-OPTIMIZATION -> WS-ANIMATOR`.

## Что делать нельзя
- снова незаметно уходить в кодовую ветку;
- дублировать источник сценарной истины вне WS-RING;
- ссылаться на старые артефакты без проверки их содержимого.
