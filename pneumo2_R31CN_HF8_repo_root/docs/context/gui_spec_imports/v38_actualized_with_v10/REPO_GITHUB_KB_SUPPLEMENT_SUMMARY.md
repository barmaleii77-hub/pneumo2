# REPO_GITHUB_KB_COMMIT_READY_SUMMARY_V38

## Назначение
Этот пакет — **commit-ready knowledge-base successor layer** для репозитория `pneumo2`.
Он не подменяет `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` и `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`, а добавляет новый consolidated imported layer `v38_github_kb_commit_ready` и patch set для его включения в активный канон репозитория.

## Что нужно сделать в репозитории
1. Скопировать каталог `REPO_IMPORT_READY/docs/context/gui_spec_imports/v38_github_kb_commit_ready/`.
2. Применить `PROJECT_SOURCES_PATCH_PROPOSAL.diff`.
3. Применить `GUI_SPEC_IMPORTS_README_PATCH_PROPOSAL.diff`.
4. При желании применить lineage-патч и индексные дополнения.
5. Не объявлять пакет runtime-closure proof до закрытия producer-side truth, browser perf trace и Windows visual acceptance.


## V10 launcher-shell actualization
Этот пакет актуализирован с учётом проверенного report-only слоя V10 по иерархии launcher-shell: доминирующий 8-шаговый маршрут, вторичные/advanced окна и вложенность send-results / compare viewer. См. `V10_ACTUALIZATION_REPORT.md` и `V10_RECONCILIATION_MATRIX.csv`.
