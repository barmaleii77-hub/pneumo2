# ROLLBACK_PLAN

Если после импорта возник конфликт:
- откатить изменения в `docs/PROJECT_SOURCES.md`;
- удалить `docs/context/gui_spec_imports/v38_github_kb_commit_ready/`;
- оставить `v3/v13/v12` как текущий imported stack;
- не менять runtime-status и release-gates.
