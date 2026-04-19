# README_V38_GITHUB_KB_COMMIT_READY

Этот архив — следующий шаг после `v37_github_kb_supplement`: **commit-ready пакет для дополнения базы знаний проекта в GitHub**.

## Что это
Пакет остаётся **самодостаточным пакетом ТЗ и машиночитаемой спецификации для CODEX** и одновременно даёт maintainer-ready слой для встраивания successor imported layer в репозиторий.

## Что внутри
- root-level mandatory spec files для CODEX;
- `REPO_IMPORT_READY/docs/context/gui_spec_imports/v38_github_kb_commit_ready/` — готовый imported successor layer;
- patch proposals для `docs/PROJECT_SOURCES.md`, `docs/context/gui_spec_imports/README.md` и lineage-слоя;
- merge/apply/order/checklist документы для maintainer;
- source-context с canonical prompt и локальным проектным контекстом.

## Главный принцип
`17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` и `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md` остаются выше imported layers по приоритету.
Этот пакет **не** объявляет runtime closure proof и не скрывает producer-side truth, browser perf и Windows visual acceptance gaps.


## V10 launcher-shell actualization
Этот пакет актуализирован с учётом проверенного report-only слоя V10 по иерархии launcher-shell: доминирующий 8-шаговый маршрут, вторичные/advanced окна и вложенность send-results / compare viewer. См. `V10_ACTUALIZATION_REPORT.md` и `V10_RECONCILIATION_MATRIX.csv`.
