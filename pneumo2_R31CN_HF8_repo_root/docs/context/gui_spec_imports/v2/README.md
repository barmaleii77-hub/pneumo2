# Pneumo GUI Codex Package v2

Этот каталог хранит active detailed machine-readable reference layer,
импортированный из `pneumo_gui_codex_package_v2.zip`.

Важно:

- `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` и
  `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md` остаются human-readable source of truth;
- содержимое этого каталога используется как imported reference artifacts, а не
  как вручную поддерживаемый канон;
- `v1` в родительском каталоге остаётся historical import и не удаляется;
- raw `.zip` в git не хранится.

## Состав imported source set

- `pneumo_gui_codex_spec_v2_detailed.json` — главный machine-readable GUI-spec;
- `manifest.json` — перечень файлов, размеров и sha256;
- `current_macro.dot`, `optimized_macro.dot` — macro workflow graphs;
- `current_element_graph.dot`, `optimized_element_graph.dot` — element-level graphs;
- `ui_element_catalog.csv` — каталог UI-элементов и shell regions;
- `field_catalog.csv` — каталог полей;
- `help_catalog.csv` — каталог развёрнутой помощи;
- `tooltip_catalog.csv` — каталог tooltip-слоя;
- `migration_matrix.csv` — machine-readable migration contract `web -> desktop`;
- `acceptance_criteria.csv` — критерии приёмки;
- `pipeline_verification.csv` — сценарии проверки пайплайна `юзер -> GUI -> юзер`;
- `test_suite.csv` — catalog-driven test cases.

## Что внутри detailed layer

- полный текущий и оптимизированный workflow;
- shell и regions базового окна `1920x1080`;
- machine-readable contract по `automation_id`, help, tooltip, visibility,
  access key, hotkey и tab order;
- migration matrix без потери функций;
- acceptance и verification suites для GUI-spec;
- implementation roadmap для дальнейшего выравнивания продукта под этот spec.

## Как использовать

1. Сначала читать `17` и `18`.
2. Затем использовать этот каталог как detailed reference layer для docs,
   parity, contract tests и shell-alignment planning.
3. Не редактировать CSV/DOT/JSON для ручной “нормализации”; производные
   интерпретации держать в docs и tests.
