# REPO_ADOPTION_PLAN_V38

## Цель
Дополнить базу знаний проекта в GitHub новым successor imported layer `v38_github_kb_commit_ready`.

## Шаги
1. Скопировать `REPO_IMPORT_READY/docs/context/gui_spec_imports/v38_github_kb_commit_ready/` в репозиторий.
2. Применить `PROJECT_SOURCES_PATCH_PROPOSAL.diff`.
3. Применить `GUI_SPEC_IMPORTS_README_PATCH_PROPOSAL.diff`.
4. При желании применить `GUI_SPEC_ARCHIVE_LINEAGE_PATCH_PROPOSAL.diff`.
5. Проверить post-merge validation из `POST_MERGE_VALIDATION.md`.
6. Не объявлять слой runtime-closure proof.


## V10 launcher-shell actualization
Этот пакет актуализирован с учётом проверенного report-only слоя V10 по иерархии launcher-shell: доминирующий 8-шаговый маршрут, вторичные/advanced окна и вложенность send-results / compare viewer. См. `V10_ACTUALIZATION_REPORT.md` и `V10_RECONCILIATION_MATRIX.csv`.
