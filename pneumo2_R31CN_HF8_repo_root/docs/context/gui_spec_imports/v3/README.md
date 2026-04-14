# Pneumo GUI Codex Package v3

Этот каталог хранит active detailed machine-readable reference layer,
импортированный из `pneumo_gui_codex_package_v3.zip`.

Важно:

- `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` и
  `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md` остаются human-readable source of truth;
- содержимое этого каталога используется как imported reference artifacts, а не
  как вручную поддерживаемый канон;
- `v2` остаётся historical detailed import, а `v1` — historical baseline
  import;
- raw `.zip` в git не хранится.

## Состав imported source set

- `pneumo_gui_codex_spec_v3_refined.json` — главный machine-readable GUI-spec;
- `manifest.json` — перечень файлов, размеров и sha256 из архивного пакета;
- `CHANGELOG_v3.md` — delta относительно `v2`;
- `current_macro.dot`, `optimized_macro.dot` — macro workflow graphs;
- `current_element_graph.dot`, `optimized_element_graph.dot` — element-level
  graphs;
- `ui_element_catalog.csv` — каталог UI-элементов и shell regions;
- `field_catalog.csv` — каталог полей;
- `help_catalog.csv` — каталог развёрнутой помощи;
- `tooltip_catalog.csv` — каталог tooltip-слоя;
- `migration_matrix.csv` — machine-readable migration contract `web -> desktop`;
- `acceptance_criteria.csv` — критерии приёмки;
- `pipeline_verification.csv` — сценарии проверки pipeline `юзер -> GUI -> юзер`;
- `test_suite.csv` — catalog-driven test cases;
- `best_practices_sources.csv` — внешний baseline best practices и UX sources;
- `source_of_truth_matrix.csv` — matrix источников истины и производных
  представлений;
- `ui_state_matrix.csv` — contract визуальных состояний элементов;
- `keyboard_matrix.csv` — F6/hotkey/access-key contract;
- `docking_matrix.csv` — contract dock/float/auto-hide/second-monitor;
- `pipeline_observability.csv` — observability events и обязательные payloads;
- `graph_delta_v3.csv` — короткий delta-слой по изменениям графа.

## Что внутри detailed layer

- уточнённый current и optimized workflow;
- element-level contract для title bar, message bar, splitters, scrollbars,
  undo/redo и empty states;
- machine-readable contract по `automation_id`, help, tooltip, visibility,
  access key, hotkey и tab order;
- source-of-truth и degraded-truth matrix для проектных доменов;
- docking, keyboard, observability и state contracts для shell;
- acceptance и verification suites для GUI-spec;
- implementation roadmap для дальнейшего выравнивания продукта под этот spec.

## Как использовать

1. Сначала читать `17` и `18`.
2. Затем использовать этот каталог как active detailed reference layer для docs,
   parity, contract tests и shell-alignment planning.
3. Не редактировать CSV/DOT/JSON для ручной “нормализации”; производные
   интерпретации держать в docs и tests.
