# Post-Chat Worktree Cleanup V38 Plan-Mode Prompts

Назначение: текущий пакет стартовых промтов для параллельных GUI-чатов после
приемки локальных chat-worktree в `codex/work` и уборки временных деревьев.

Использовать этот файл вместо `17_POST_ACCEPTANCE_V38_PLAN_MODE_PROMPTS.md`.
Файлы `14...17...` остаются историей и контекстом, но не рабочим стартом.

## Текущий baseline

Новые чаты начинают только от `codex/work`.

Ожидаемое состояние перед работой:

- `codex/work` синхронизирован с `origin/codex/work`;
- основной worktree: `C:\Users\Admin\Documents\GitHub\pneumo2`;
- временные chat-worktree удалены;
- локальные chat-ветки удалены или не используются как source-of-truth;
- V38 является текущим GUI/TZ/spec слоем;
- V37 остается predecessor provenance;
- WEB не развивается, кроме временных launch-кнопок desktop GUI;
- принятые изменения чатов уже находятся в `codex/work` и не должны
  переизобретаться.

## Общий первый запуск

Каждый чат стартует в Plan mode.

Plan mode означает:

- только инспекция;
- не редактировать файлы;
- не stage/commit/push;
- не создавать, не удалять и не двигать ветки/worktree;
- не запускать bulk cleanup;
- не cherry-pick старые chat-ветки;
- не переносить generated runtime artifacts как канон;
- не заявлять приемку GUI по unit tests без визуальной/runtime проверки.

Обязательные первые команды:

```powershell
git fetch --all --prune
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/codex/work
git worktree list --porcelain
git branch -vv --all
```

Если `HEAD` отличается от `origin/codex/work`, есть dirty paths или видны
старые chat-worktree, остановись и сначала доложи это пользователю.

## Обязательное чтение

Прочитать до lane-specific файлов:

- `pneumo2_R31CN_HF8_repo_root/docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/13_CHAT_REQUIREMENTS_LOG.md`
- `pneumo2_R31CN_HF8_repo_root/docs/14_CHAT_PLANS_LOG.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/CHAT_WORKTREE_ACCEPTANCE_CLEANUP_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/README.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/ACCEPTANCE_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_CATALOG.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_VISIBILITY_MATRIX.csv`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/PIPELINE_OPTIMIZED.dot`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v38_github_kb_commit_ready/REPO_OPEN_GAPS_TO_KEEP_OPEN.csv`

## Глобальные запреты

- Не развивать WEB UI.
- Не дублировать `desktop_animator`, `qt_compare_viewer`, `desktop_mnemo`.
- Не показывать оператору служебную миграционную информацию.
- Не использовать в пользовательской поверхности формулировки:
  `Статус миграции`, `Открыть выбранный этап`, `Данные машины`,
  `Current context`, `runtime`, `managed mode`, `sidecar`, `migration status`.
- Не заменять операторские русские статусы техническими ключами.
- Не скрывать open gaps и не объявлять их закрытыми без named evidence.
- Не переименовывать канонические параметры без V38 catalog/contract update.
- Не трогать чужие owned files без явной координации.

## Обязательный V38 gate

Каждый lane-план обязан включить:

1. branch/HEAD/remote/worktree state.
2. owned files и forbidden files.
3. релевантные требования V38 и open gaps.
4. что уже принято в baseline и должно сохраниться.
5. визуальную проверку окна на Windows.
6. проверку русского operator-facing текста и отсутствия mojibake.
7. проверку `PIPELINE_OPTIMIZED.dot`.
8. список лишних шагов навигации, если они есть.
9. минимальный patch plan после approval.
10. focused tests и evidence artifacts.

Ключевой pipeline:

```text
SHELL -> PROJECT -> INPUTS -> RING -> SUITE -> BASELINE -> OPT -> ANALYSIS
ANALYSIS -> ANIMATOR
ANALYSIS -> DIAGNOSTICS
ANALYSIS -> COMPARE
```

Дерево, поиск и выбор в shell считаются навигацией. Обязательная кнопка
переходника вроде "открыть выбранный этап" является blocker, если она не
нужна пользователю по V38 flow.

## 1. Главное окно и навигация

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Главное окно и навигация.

Цель:
Сделать главное desktop-окно понятным классическим Windows GUI: верхнее меню, toolbar, дерево маршрута, поиск команд, единое место запуска всех GUI-модулей, инспектор, status/progress strip и прямой V38 pipeline без лишних промежуточных кнопок.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/01_MAIN_WINDOW.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/START_PNEUMO_APP.py`
- `pneumo2_R31CN_HF8_repo_root/START_DESKTOP_MAIN_SHELL.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_qt_shell/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell_qt.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/launch_ui.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_main_shell_qt_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_main_shell_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_shell_parity_contract.py`

Forbidden files:
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo_solver_ui/desktop_mnemo/*`
- optimizer/results internals
- diagnostics producer internals
- solver/model physics

Plan must verify:
- все GUI-модули открываются из одного понятного места;
- дерево/поиск/выбор сами ведут пользователя, без кнопки-переходника;
- нет `Статус миграции`, `Открыть выбранный этап`, `Данные машины`;
- status/progress strip показывает операторскую информацию, а не служебщину;
- Snap/native Windows behavior не ломается.

Tests after approval:
- `python -m pytest tests/test_desktop_main_shell_qt_contract.py tests/test_desktop_main_shell_contract.py tests/test_desktop_shell_parity_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 2. Исходные данные

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Исходные данные.

Цель:
Довести окно исходных данных: секции Геометрия, Пневматика, Механика, Компоненты, Справочные данные и расчетные настройки; слайдеры плюс числовые поля; единицы; диапазоны; источник значения; dirty/current state; снимок исходных данных для следующих этапов.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/02_INPUT_DATA.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_graphics.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_suite_snapshot.py` only for inputs handoff
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_editor_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_input_graphics_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_suite_snapshot.py`

Forbidden files:
- ring editor internals;
- optimizer/results internals;
- animator/mnemo/compare internals;
- canonical physics/model files;
- main shell beyond launch/adapter coordination.

Plan must verify:
- видимые кластеры соответствуют V38 vocabulary;
- нет формулировки `Данные машины`;
- слайдеры, диапазоны и единицы не конфликтуют с catalog/visibility matrix;
- выбор раздела не требует отдельной кнопки "открыть этап";
- `inputs_snapshot.json` handoff честный и воспроизводимый.

Tests after approval:
- `python -m pytest tests/test_desktop_input_editor_contract.py tests/test_desktop_input_graphics_contract.py tests/test_desktop_suite_snapshot.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 3. Настройка расчета и сценарии кольца

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Настройка расчета и сценарии кольца.

Цель:
Довести связку редактора/генератора сценариев кольца и подготовки прогона: сегменты, стыки, проверки, экспорт road/scenario artifacts, набор испытаний, расчетные лимиты и handoff в baseline. Ring editor остается единственным source-of-truth сценариев.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/03_RUN_SETUP.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/04_RING_EDITOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/README.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_run_setup_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/adapters/desktop_ring_editor_adapter.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_ring_editor_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_run_setup_center_contract.py`

Forbidden files:
- `desktop_input_editor.py`;
- optimizer runtime internals;
- results center internals;
- animator/mnemo/compare windows;
- solver/model physics.

Plan must verify:
- user-flow `INPUTS -> RING -> SUITE -> BASELINE`;
- сценарий редактируется в одном месте, preview/export derived-only;
- расчетные настройки не смешаны с исходными параметрами без V38 основания;
- длительные проверки имеют видимый прогресс в том же окне;
- пользовательские сообщения на русском.

Tests after approval:
- `python -m pytest tests/test_desktop_ring_editor_contract.py tests/test_desktop_run_setup_center_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 4. Compare Viewer

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Compare Viewer.

Цель:
Довести Compare Viewer как окно сравнения выбранных прогонов: compare contract, session autoload, selected runs, objective/influence context, понятные русские статусы, export actions and no WEB dependency. Не дублировать Results Center и Engineering Analysis.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/05_COMPARE_VIEWER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_contract.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_session.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/06_CompareViewer_QT.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_qt_compare_viewer_compare_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_qt_compare_viewer_session_autoload_source.py`

Forbidden files:
- optimizer runtime internals;
- engineering analysis internals;
- desktop animator and mnemo;
- main shell except launch registration.

Plan must verify:
- labels for selected runs, hashes, warnings and export are Russian/operator-facing;
- no visible `Current context`, `sidecar`, raw session/debug wording;
- Compare opens from analysis/results context;
- Compare does not become a second Results Center;
- missing artifacts are warnings, not fake success.

Tests after approval:
- `python -m pytest tests/test_qt_compare_viewer_compare_contract.py tests/test_qt_compare_viewer_session_autoload_source.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 5. Desktop Mnemo

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Desktop Mnemo.

Цель:
Довести мнемосхему как отдельное desktop-окно: быстрый запуск, нормальное закрытие, читаемая схема без наложений, честные truth-state режимы, русские подписи и отсутствие зависаний.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/06_DESKTOP_MNEMO.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/release_readiness/DESKTOP_MNEMO_WINDOWS_ACCEPTANCE_2026-04-18.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_mnemo.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_mnemo_launcher_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_mnemo_*`
- mnemo-specific docs under `docs/context/release_readiness/*MNEMO*`

Forbidden files:
- `pneumo_solver_ui/desktop_animator/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- solver/model files;
- main shell except launch wiring.

Plan must verify:
- реальное окно открывается и закрывается без зависания;
- нет наложения текста на схеме;
- все видимые сообщения на русском;
- unavailable/partial data states честные;
- Mnemo не превращается в Animator.

Tests after approval:
- `python -m pytest tests/test_desktop_mnemo_launcher_contract.py tests/test_desktop_mnemo_runtime_proof.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 6. Desktop Animator

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Desktop Animator.

Цель:
Довести desktop animator как достоверную визуализацию выбранного результата: artifact pointers, analysis context, cylinder render policy, truth modes, capture provenance, performance gating and clear Russian operator status. Не дублировать Desktop Mnemo и Compare Viewer.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/07_DESKTOP_ANIMATOR.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/*`
- `pneumo2_R31CN_HF8_repo_root/tests/test_v32_desktop_animator_truth_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_r*_animator*.py`
- animator-specific runtime/evidence docs when needed.

Forbidden files:
- `pneumo_solver_ui/desktop_mnemo/*`
- `pneumo_solver_ui/qt_compare_viewer.py`
- results/optimizer producer internals without handoff contract;
- model/solver physics.

Plan must verify:
- visible truth mode, data source and warnings are Russian/operator-facing;
- no fake data when artifacts are absent;
- cylinder rendering follows accepted policy;
- animation opens from analysis context;
- capture/provenance is evidence, not marketing text.

Tests after approval:
- `python -m pytest tests/test_v32_desktop_animator_truth_contract.py tests/test_r37_desktop_animator_perf_gating.py tests/test_r78_animator_playback_speed_stability.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 7. Оптимизатор и центр результатов

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Оптимизатор и центр результатов.

Цель:
Довести контур `SUITE -> BASELINE -> OPT -> ANALYSIS`: набор испытаний, baseline, настройки оптимизации, один active optimization mode, выбранный прогон, Results Center, resume safety and handoff to Compare/Animator/Diagnostics.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/08_OPTIMIZER_CENTER.md`
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_optimizer_tabs/*`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_optimizer_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_results_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_results_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/autotest_gui.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_optimizer_center_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_test_center_results_center_contract.py`

Forbidden files:
- ring editor generation internals;
- compare viewer internals;
- animator/mnemo internals;
- diagnostics producer internals;
- solver/model physics.

Plan must verify:
- настройки оптимизации видимы и логично сгруппированы;
- active mode один, без конкурирующих selectors;
- длительные операции показывают progress в этом же окне;
- выбранный прогон передается в Compare/Animator/Diagnostics без ручной путаницы;
- Results Center не подменяет Engineering Analysis.

Tests after approval:
- `python -m pytest tests/test_desktop_optimizer_center_contract.py tests/test_test_center_results_center_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 8. Диагностика и SEND Bundle

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Диагностика и SEND Bundle.

Цель:
Довести diagnostics center и SEND bundle: простое окно без запутанных вкладок, общий видимый блок текущего процесса, progressbar для длительных действий, latest ZIP, validation, inspect/send bundle and honest open gaps. Все пользовательские сообщения на русском.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_diagnostics_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_diagnostics_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/health_report.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/inspect_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/make_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_bundle_evidence.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/validate_send_bundle.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_diagnostics_center_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_diagnostics_text_encoding_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_v32_diagnostics_send_bundle_evidence.py`

Forbidden files:
- producer internals in optimizer/results/animator/engineering except evidence reads;
- main shell beyond diagnostics launch/status wiring;
- release packaging outside SEND bundle scope.

Plan must verify:
- progressbar виден независимо от выбранной вкладки;
- длительное действие не рисует прогресс в другом месте;
- все статусы и ошибки на русском;
- missing artifacts остаются open blockers;
- latest bundle validation не объявляет release closure без evidence.

Tests after approval:
- `python -m pytest tests/test_desktop_diagnostics_center_contract.py tests/test_diagnostics_text_encoding_contract.py tests/test_v32_diagnostics_send_bundle_evidence.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 9. Геометрия, каталоги и справочники

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Геометрия, каталоги и справочники.

Цель:
Довести geometry/reference center: каталоги, reference values, producer truth, hardpoints/solver_points gap visibility, validation and clear handoff to input/animator/diagnostics.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/11_GEOMETRY_REFERENCE.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_geometry_reference_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_geometry_reference_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/adapters/desktop_geometry_reference_adapter.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_geometry_reference_center_contract.py`

Forbidden files:
- input editor canonical parameter editing;
- animator rendering internals;
- solver/model physics;
- diagnostics producer packaging except evidence reads.

Plan must verify:
- справочники не выглядят как главный редактор исходных данных;
- hardpoints/solver_points gaps видимы и честно open;
- reference/source labels на русском и без debug wording;
- handoff to diagnostics/animator не закрывает gaps без producer evidence.

Tests after approval:
- `python -m pytest tests/test_desktop_geometry_reference_center_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## 10. Инженерный анализ, калибровка и influence

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Первый запуск строго в Plan mode: ничего не редактируй, не удаляй, не stage/commit/push, не создавай ветку и не трогай worktree до принятого плана.

Русское название направления: Инженерный анализ, калибровка и influence.

Цель:
Довести Engineering Analysis center: calibration, influence, selected-run evidence, analysis context, clear charts/tables, handoff to Compare Viewer and Diagnostics. Не подменять Compare Viewer и Results Center.

Дополнительно прочитай:
- `pneumo2_R31CN_HF8_repo_root/docs/gui_chat_prompts/12_ENGINEERING_ANALYSIS.md`
- `pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`

Owned files:
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_model.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_engineering_analysis_runtime.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
- `pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/adapters/desktop_engineering_analysis_center_adapter.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_engineering_analysis_center_contract.py`
- `pneumo2_R31CN_HF8_repo_root/tests/test_desktop_engineering_analysis_contract.py`

Forbidden files:
- Compare Viewer implementation internals;
- optimizer/results producer internals except selected-run contract reads;
- diagnostics packaging internals except evidence handoff;
- solver/model physics.

Plan must verify:
- analysis/calibration/influence panels читаемы и не выглядят как raw status dump;
- evidence status на русском, без service jargon;
- selected-run source понятен;
- Compare/Results/Diagnostics boundaries не смешаны;
- open gaps remain open until named evidence.

Tests after approval:
- `python -m pytest tests/test_desktop_engineering_analysis_center_contract.py tests/test_desktop_engineering_analysis_contract.py tests/test_ui_text_no_mojibake_contract.py -q`
```

## Финальная интеграционная приемка

```text
Ты работаешь в проекте `C:\Users\Admin\Documents\GitHub\pneumo2`.
Русское название направления: Интеграционная приемка GUI после V38.

Задача:
Принять результаты параллельных GUI-чатов только после того, как каждый чат указал owned files, forbidden files, V38 visual evidence, optimized pipeline evidence and tests. Не смешивай unrelated changes. Не удаляй ветки или worktree до сверки, что их изменения уже находятся в `codex/work`.

Обязательные проверки:
- `git fetch --all --prune`
- `git status --short --branch`
- `git worktree list --porcelain`
- `git branch -vv --all`
- focused pytest по затронутым lanes
- `python -m pytest tests/test_ui_text_no_mojibake_contract.py -q`
- `git diff --check`
- точечный поиск запрещенных UI-фраз

Приемка допустима только если:
- `codex/work` синхронизирован с `origin/codex/work`;
- нет потерянных dirty-файлов во временных worktree;
- нет служебных UI-формулировок;
- open gaps остаются open, если нет runtime evidence;
- база знаний обновлена через `knowledge_base_sync`;
- итоговый push выполнен в `origin/codex/work`.
```
