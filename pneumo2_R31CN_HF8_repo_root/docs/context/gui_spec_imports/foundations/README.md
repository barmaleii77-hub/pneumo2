# Foundational GUI Prompt Sources

Этот каталог хранит upstream prompt-источники, которые предшествуют серии
архивов `v1…v13` и помогают восстановить исходное проектное намерение.

Важно:

- это не human-readable product canon;
- каноном для текущего проекта остаются
  [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../../../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
  и
  [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../../../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md);
- foundational prompts используются как provenance и recovery layer для
  понимания исходных жёстких требований: native Windows desktop, no web-first,
  no feature loss, diagnostics as first-class surface, ring editor as single
  source of truth, honest graphics и command-search discipline.

## Текущий слой

- `prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md`
  — upstream prompt source, который в lineage обозначается как `PROMPT_V2`.

## Как использовать

1. Сначала читать `17` и `18`.
2. Затем читать active detailed layer `v3`.
3. Для `WS-RING` дополнительно читать `v13_ring_editor_migration`.
4. Если нужно понять исходный замысел ещё до `v1`, читать этот foundational
   prompt вместе с lineage `v1…v13` и `v12_design_recovery`.
