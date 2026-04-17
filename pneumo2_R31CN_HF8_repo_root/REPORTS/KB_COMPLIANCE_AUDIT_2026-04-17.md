# Аудит соответствия проекта базе знаний

Дата: 2026-04-17

## Область аудита

Проверены текущие рабочие изменения и runtime/UI слой против:

- `00_READ_FIRST__ABSOLUTE_LAW.md`
- `DATA_CONTRACT_UNIFIED_KEYS.md`
- `docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
- `docs/PROJECT_SOURCES.md`
- `docs/context/gui_spec_imports/v37_github_kb_supplement/*`
- `docs/context/gui_spec_imports/v3/*`
- `docs/context/gui_spec_imports/v13_ring_editor_migration/*`
- `pneumo_solver_ui/desktop_spec_shell/*`
- related contract tests.

Текущее состояние рабочей копии важно: `v37_github_kb_supplement` уже импортирован и связан с `18`, `PROJECT_SOURCES`, GUI prompt index и doc-contract tests, но эти изменения пока не закоммичены.

## Follow-up fix в этом рабочем шаге

После первичного аудита закрыт `P0` по startup responsiveness:

- `overview_state.py` больше не делает recursive scan всего `Path.home()/Desktop`;
- поиск bundle ZIP ограничен известными runtime-каталогами и прямым non-recursive Desktop scan;
- `main_window.py` больше не вызывает `QSettings.sync()` в пути construction / first `open_workspace`;
- layout/state save теперь отложен через single-shot timer, а принудительный sync выполняется только при закрытии окна.

Проверка после исправления:

- `pytest -q --timeout=30 tests/test_desktop_gui_spec_shell_contract.py tests/test_desktop_gui_spec_workspace_pages_contract.py tests/test_desktop_gui_spec_shell_runtime_contract.py tests/test_desktop_gui_spec_diagnostics_hosted_contract.py`
- Результат: `20 passed in 3.88s`

Закрыт `P1` по alignment runtime registry с `v37 WORKSPACE_CONTRACT_MATRIX.csv`:

- `overview` теперь имеет canonical owner `WS-PROJECT`;
- `results_analysis` теперь имеет canonical owner `WS-ANALYSIS`;
- `tools` теперь имеет canonical owner `WS-TOOLS`;
- shell-level owner зафиксирован как `WS-SHELL`;
- старые `WS-RESULTS`, `WS-ANALYTICS`, `GLOBAL` больше не являются runtime owner ids и сохранены только как legacy/catalog aliases там, где нужны для чтения `v3` catalog layer.

Проверка после исправления:

- `pytest -q --timeout=45 tests/test_gui_spec_docs_contract.py tests/test_desktop_gui_spec_catalog_contract.py tests/test_desktop_gui_spec_shell_contract.py tests/test_desktop_gui_spec_workspace_pages_contract.py tests/test_desktop_gui_spec_shell_runtime_contract.py tests/test_desktop_gui_spec_diagnostics_hosted_contract.py tests/test_desktop_shell_parity_contract.py tests/test_knowledge_base_sync_contract.py tests/test_web_launcher_desktop_bridge_contract.py tests/test_root_launcher_bootstrap_contract.py tests/test_launcher_deps_gate_contract.py tests/test_diagnostics_text_encoding_contract.py tests/test_ui_text_no_mojibake_contract.py`
- Результат: `58 passed in 5.14s`

Закрыт `P1` по честной маркировке `launch_surface` для external/legacy routes:

- `ring.editor.open`, `test.center.open`, `baseline.center.open`,
  `optimization.center.open`, `results.center.open` теперь явно имеют
  `launch_surface="legacy_bridge"` и `status_label="Legacy bridge"`;
- `diagnostics.legacy_center.open` теперь явно имеет
  `launch_surface="legacy_bridge"` и остаётся `Fallback / debug`;
- добавлен regression test: любая команда `kind="launch_module"` не может
  заявлять `launch_surface="workspace"`.

Проверка после исправления:

- `pytest -q --timeout=45 tests/test_desktop_gui_spec_shell_contract.py tests/test_desktop_gui_spec_catalog_contract.py tests/test_desktop_gui_spec_workspace_pages_contract.py tests/test_desktop_gui_spec_shell_runtime_contract.py tests/test_desktop_gui_spec_diagnostics_hosted_contract.py`
- Результат: `25 passed in 4.32s`
- Полный целевой набор после исправления:
  `59 passed in 5.43s`

## Краткий итог

| Зона | Статус | Вывод |
| --- | --- | --- |
| Human-readable GUI canon `17/18` | Частично соответствует | `18` уже знает про `v37`, приоритет `17/18` сохранён. |
| Imported reference layers | Частично соответствует | `v37` импортирован как repo-local layer, но runtime его пока не потребляет. |
| Единая база знаний | Не соответствует полностью | `docs/00_PROJECT_KNOWLEDGE_BASE.md` и chat KB не знают про `v37`. |
| `desktop_spec_shell` shell route | Частично соответствует | Есть 11 top-level workspaces, command search, inspector, hosted diagnostics. |
| Workspace contract v37 | Исправлено в follow-up | Runtime registry покрывает `v37` workspace ids; старые ids оставлены только как catalog aliases. |
| Route-critical hosted workspaces | Не соответствует цели | Большинство рабочих пространств всё ещё `legacy_bridge` / `external_window`. |
| Diagnostics hosted lane | В основном соответствует | Hosted diagnostics работает и тесты проходят, legacy center оставлен fallback. |
| Runtime responsiveness | Исправлено в follow-up | Shell smoke tests больше не зависают на старте; регрессия закрыта targeted tests. |
| Automation/help/tooltip contract | Частично соответствует | Основные workspace metadata есть, но часть команд без `automation_id`/`tooltip_id`. |
| Open gaps from v37 | Частично соответствует | Gaps импортированы, но не подняты в главный KB entrypoint и GUI/self-check. |

## Findings

### P0. `desktop_spec_shell` может зависать на старте

Файлы:

- `pneumo_solver_ui/desktop_spec_shell/overview_state.py`
- `pneumo_solver_ui/desktop_spec_shell/main_window.py`

Статус: исправлено в follow-up шаге 2026-04-17.

Доказательство:

- `tests/test_desktop_gui_spec_workspace_pages_contract.py::test_gui_spec_main_window_uses_hosted_pages_for_runtime_and_control_hubs_for_route_pages` падает по timeout 20s.
- Stack trace указывает на `DesktopGuiSpecMainWindow.__init__ -> open_workspace -> OverviewPage.refresh_view -> build_overview_snapshot -> _latest_path -> Path.home()/Desktop.rglob(...)`.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py::test_main_window_applies_v3_shortcuts_and_docking_contracts` падает по timeout 20s.
- Stack trace указывает на `open_workspace -> _save_window_state -> QSettings.sync()`.

Почему это конфликт с базой знаний:

- `17/18` и `v37` требуют responsive desktop shell, idle discipline, progress для долгих операций и отсутствие блокирующих UI-проходов.
- Пользовательская жалоба "всё виснет" подтверждается контрактными smoke-тестами.

Рекомендуемое исправление:

- Рекурсивный поиск по всему `Path.home()/Desktop` убран.
- Bundles ищутся только в известных repo/runtime директориях и прямом non-recursive Desktop scan.
- `_save_window_state()` больше не делает sync в первом `open_workspace()` из конструктора.
- `QSettings.sync()` отложен и не выполняется в tight UI construction path.

### P1. Runtime registry не выровнен с `v37` workspace contract

Файл:

- `pneumo_solver_ui/desktop_spec_shell/registry.py`

Статус: исправлено в follow-up шаге 2026-04-17.

Доказательство:

`v37` workspace ids:

- `WS-SHELL`
- `WS-PROJECT`
- `WS-INPUTS`
- `WS-RING`
- `WS-SUITE`
- `WS-BASELINE`
- `WS-OPTIMIZATION`
- `WS-ANALYSIS`
- `WS-ANIMATOR`
- `WS-DIAGNOSTICS`
- `WS-SETTINGS`
- `WS-TOOLS`

Текущий runtime mapping:

- `overview -> GLOBAL`
- `results_analysis -> WS-RESULTS; WS-ANALYTICS`
- `tools -> GLOBAL`
- нет явного `WS-SHELL`, `WS-PROJECT`, `WS-ANALYSIS`, `WS-TOOLS`.

Почему это конфликт:

- `v37` стал successor KB/TZ/spec connector layer.
- Workspace contract matrix должна быть восстанавливаемой из repo-local knowledge base.
- Сейчас search/help/provenance registry не может однозначно мапиться на `v37` workspace ids.

Рекомендуемое исправление:

- Введён явный mapping:
  `overview -> WS-PROJECT`,
  `results_analysis -> WS-ANALYSIS`,
  `tools -> WS-TOOLS`,
  shell-level metadata -> `WS-SHELL`.
- Старые `WS-RESULTS`, `WS-ANALYTICS`, `GLOBAL` оставлены только как legacy aliases/search synonyms, а не owner ids.
- Добавлен contract test: все `v37 WORKSPACE_CONTRACT_MATRIX.workspace_id` покрыты runtime registry или shell-level owner.

### P1. Legacy/external команды маркируются как `workspace`

Файл:

- `pneumo_solver_ui/desktop_spec_shell/registry.py`

Статус: исправлено в follow-up шаге 2026-04-17.

Доказательство:

Команды `kind=launch_module`, но `launch_surface=workspace` из-за default:

- `ring.editor.open`
- `test.center.open`
- `baseline.center.open`
- `optimization.center.open`
- `results.center.open`
- `diagnostics.legacy_center.open`

Почему это конфликт:

- `17/18` требуют честной маркировки hosted / bridge / fallback / external.
- По текущему metadata shell может показывать legacy bridge как active workspace surface.

Рекомендуемое исправление:

- Для всех legacy route commands явно проставлен `launch_surface="legacy_bridge"` или уже существующий `external_window`/`tooling`.
- Для fallback-команд сохранён `status_label="Fallback / debug"` и они не смешиваются с primary active path.
- Добавлен test: любой `launch_module` без native page не может иметь default `workspace` surface.

### P1. Не все interactive commands имеют `automation_id` и `tooltip_id`

Файлы:

- `pneumo_solver_ui/desktop_spec_shell/registry.py`
- `pneumo_solver_ui/desktop_spec_shell/catalogs.py`
- `docs/context/gui_spec_imports/v3/ui_element_catalog.csv`
- `docs/context/gui_spec_imports/v37_github_kb_supplement/UI_ELEMENT_CATALOG.csv`

Доказательство:

Команды без полного automation/help/tooltip metadata:

- `input.editor.open`
- `ring.editor.open`
- `test.center.open`
- `results.center.open`
- `analysis.engineering.open`
- `animation.mnemo.open`
- `diagnostics.verify_bundle`
- `diagnostics.send_results`
- `diagnostics.legacy_center.open`
- `tools.geometry_reference.open`
- `tools.autotest.open`
- `tools.legacy_shell.open`

Почему это конфликт:

- `17/18` и `v37` требуют `automation_id`, tooltip и expanded help для значимых interactive elements.

Рекомендуемое исправление:

- Расширить command-to-element mapping или добавить недостающие rows в active catalog layer.
- Поднять test coverage с трёх команд до всех visible commands.

### P2. `v37` не отражён в главном entrypoint базы знаний

Файлы:

- `docs/00_PROJECT_KNOWLEDGE_BASE.md`
- `docs/15_CHAT_KNOWLEDGE_BASE.json`
- `pneumo_solver_ui/tools/knowledge_base_sync.py`

Доказательство:

- `docs/00_PROJECT_KNOWLEDGE_BASE.md` не содержит `v37`.
- `docs/15_CHAT_KNOWLEDGE_BASE.json` не содержит `v37`.
- `knowledge_base_tracked_paths()` отслеживает только `00_PROJECT_KNOWLEDGE_BASE.md`, chat logs и JSON store; `PROJECT_SOURCES.md`, GUI-spec imports README и lineage не входят в tracked KB set.

Почему это конфликт:

- `00_PROJECT_KNOWLEDGE_BASE.md` объявлен единым стартовым источником для AI и разработчиков.
- Новые планы/архивы из чатов должны попадать в KB слой в том же рабочем цикле.

Рекомендуемое исправление:

- Добавить `v37_github_kb_supplement` в `00_PROJECT_KNOWLEDGE_BASE.md`.
- Зафиксировать требование/план v37 в `15_CHAT_KNOWLEDGE_BASE.json` и regenerate `13/14` logs через `knowledge_base_sync`.
- Расширить `knowledge_base_tracked_paths()` на `PROJECT_SOURCES.md`, `GUI_SPEC_ARCHIVE_LINEAGE.md`, `gui_spec_archive_lineage.json`, `docs/context/gui_spec_imports/README.md`.

### P2. Runtime всё ещё завязан на `v3`, `v37` является только doc-layer

Файл:

- `pneumo_solver_ui/desktop_spec_shell/catalogs.py`

Доказательство:

- `ACTIVE_GUI_SPEC_IMPORT_VERSION = "v3"`.
- `v37` в runtime catalog loader не используется.

Почему это не обязательно ошибка, но риск:

- В `PROJECT_SOURCES` и `18` `v37` теперь стоит выше `v3` как successor KB/TZ/spec supplement.
- Если runtime продолжает читать только `v3`, часть требований `v37` может никогда не попасть в shell/search/help/acceptance.

Рекомендуемое исправление:

- Оставить `v3` как detailed UI catalog source, но добавить отдельный `v37` adapter для workspace matrix, requirements, acceptance and open gaps.
- Добавить test: `v37` workspace/gaps/acceptance layer доступен из runtime audit/self-check registry.

### P2. В runtime catalog loaders ещё есть fallback на mojibake keys

Файлы:

- `pneumo_solver_ui/desktop_spec_shell/catalogs.py`
- `pneumo_solver_ui/desktop_spec_shell/help_registry.py`
- `pneumo_solver_ui/desktop_spec_shell/registry.py`

Доказательство:

- В коде есть fallback keys вида `РєР°...`.
- Mojibake не отображается пользователю и текущие encoding tests проходят, но code path сохраняет старый debt.

Почему это конфликт:

- База знаний требует убрать кракозябры и нормализовать UTF-8 keys, а не держать скрытый fallback.

Рекомендуемое исправление:

- Нормализовать imported CSV headers окончательно в active layer или вынести legacy-header migration в отдельный one-time import adapter.
- Убрать mojibake fallbacks из runtime hot path.

### P2. Open gaps из `v37` импортированы, но не подняты в GUI/self-check

Файлы:

- `docs/context/gui_spec_imports/v37_github_kb_supplement/REPO_OPEN_GAPS_TO_KEEP_OPEN.csv`
- `pneumo_solver_ui/desktop_spec_shell/overview_state.py`
- `pneumo_solver_ui/desktop_spec_shell/diagnostics_panel.py`

Открытые gaps:

- producer-side `hardpoints / solver_points` truth
- `cylinder packaging passport`
- browser perf trace / viewport gating
- Windows visual/runtime acceptance

Почему это конфликт:

- `v37` явно запрещает скрывать эти gaps.
- В GUI overview/diagnostics они пока не являются visible self-check signals.

Рекомендуемое исправление:

- Показывать open gaps в `Overview` или diagnostics/self-check panel.
- Добавить status: `open`, `evidence missing`, `runtime proof required`.

## Проверки

Успешно:

- `pytest -q tests/test_gui_spec_docs_contract.py tests/test_desktop_gui_spec_catalog_contract.py tests/test_desktop_gui_spec_shell_contract.py tests/test_desktop_shell_parity_contract.py tests/test_knowledge_base_sync_contract.py tests/test_diagnostics_text_encoding_contract.py tests/test_ui_text_no_mojibake_contract.py`
- Результат: `37 passed in 12.42s`

- `pytest -q --timeout=30 tests/test_desktop_gui_spec_diagnostics_hosted_contract.py`
- Результат: `4 passed in 27.53s`

Проблемы:

- Первичный combined GUI runtime/smoke command до исправления timed out after 184s.
- Первичные одиночные smoke tests до исправления timed out after 20s.
- После follow-up fix GUI shell/runtime block прошёл: `20 passed in 3.88s`.

## Рекомендуемый порядок исправлений

1. Добить `automation_id`/`tooltip_id`/`help_id` для всех visible commands.
2. Обновить `00_PROJECT_KNOWLEDGE_BASE.md`, chat KB store/logs и `knowledge_base_tracked_paths()`.
3. Добавить runtime adapter/self-check для `v37` acceptance/open gaps.
4. Убрать mojibake fallback keys из runtime loaders после нормализации imported sources.
