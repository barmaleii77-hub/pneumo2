# Desktop/Web Parity Summary

Этот документ является human-readable summary поверх machine-readable migration
contract из `gui_spec_imports/v3`.

Канон и приоритет источников:

- [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
- [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
- [migration_matrix.csv](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v3/migration_matrix.csv)
- [desktop_web_parity_map.json](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/desktop_web_parity_map.json)

Правило:

- канон `17/18` определяет смысл маршрута;
- `migration_matrix.csv` задаёт machine-readable contract `web -> desktop`;
- этот summary объясняет пользователю и разработчику, где теперь живёт каждая
  функция и как её найти через command search.

## Статусы миграции v3

- `обязательно` — функция обязана быть сохранена в desktop-маршруте как
  поддерживаемая и находимая поверхность.
- `новый_обязательный_слой` — в веб-версии не было единого полноценного аналога,
  но для desktop GUI этот слой обязателен и считается release-gate contract.

## Сводка маршрутов

| Web feature | Старое место | Новое desktop место | Как найти через command search | Что улучшено |
|---|---|---|---|---|
| `WEB-001` Редактирование параметров подвески и диапазонов оптимизации | Главная страница и таблица параметров web-приложения | Рабочее пространство «Исходные данные» | `поиск: параметры подвески / диапазоны оптимизации / жёсткость / цилиндр` | Одновременный числовой и графический вид, правый инспектор, явная help-панель. |
| `WEB-002` Режимы и флаги | Отдельный блок флагов в web UI | Левое дерево → раздел «Режимы и флаги» внутри «Исходные данные» | `поиск: режимы / флаги / асимметрия / degraded` | Явное разделение числовых и логических параметров, объяснимость через help. |
| `WEB-003` Редактор кольца и генератор дорожного сценария | Генератор сценария и связанная форма web UI | Рабочее пространство «Редактор кольца и сценариев» | `поиск: редактор кольца / сценарий / профиль дороги / сегмент` | Единый канон сегментов, план кольца, продольный профиль, поперечный уклон, seam diagnostics и правый инспектор как единственное место детального редактирования сегмента. |
| `WEB-004` Матрица испытаний | Suite editor и таблица тестов | Рабочее пространство «Матрица испытаний» | `поиск: испытания / suite / матрица испытаний` | Связь с кольцом, валидация sidecar-файлов, preview и добавление в pipeline без скрытых маршрутов; `WS-SUITE` потребляет ring contract и не дублирует геометрию сценария. |
| `WEB-005` Baseline | Baseline controls в главной оптимизационной поверхности | Рабочее пространство «Базовый прогон» | `поиск: baseline / базовый прогон / принять baseline` | Явный baseline source, сравнение кандидата с baseline, политика auto-update на отдельной панели. |
| `WEB-006` StageRunner | Главная страница и/или Optimization page web UI | Рабочее пространство «Центр оптимизации» | `поиск: StageRunner / режим по стадиям / запустить StageRunner` | Один активный режим запуска, stage policy, visible objective contract, run preview. |
| `WEB-007` Distributed coordinator / Dask / Ray / BoTorch | Optimization page / coordinator blocks / CLI-related forms | Рабочее пространство «Центр оптимизации», режим distributed | `поиск: distributed coordinator / Dask / Ray / BoTorch` | Честное переключение режимов, без одновременных conflicting launch-кнопок. |
| `WEB-008` Монитор выполнения и live progress | Прогресс на странице оптимизации и background status | Рабочее пространство «Монитор выполнения» + нижняя строка состояния | `поиск: монитор выполнения / progress / стадия` | Прогресс на текущем экране, stage rows, underfill/gate reasons, taskbar progress. |
| `WEB-009` История запусков и baseline history | Optimization history / archive / baseline history blocks | Левое дерево истории + центр оптимизации + анализ | `поиск: история запусков / сравнить run / objective contract` | История показывает objective stack, hard gate, baseline source и причину различий. |
| `WEB-010` Просмотр результатов и сравнение | Result viewers / compare pages | Рабочие пространства «Результаты» и «Аналитика» | `поиск: результаты / сравнение / KPI / график` | Сначала объяснение, потом детали; связка график ↔ таблица ↔ 3D. |
| `WEB-011` 3D-аниматор и дорожный HUD | Desktop animator / animation cockpit / mech_car3d | Рабочее пространство «Аниматор» | `поиск: аниматор / 3D / ViewCube / дорожный HUD` | Truth banner, dock/detach, ViewCube, timeline, связка с анализом и инспектором. |
| `WEB-012` Мнемосхема пневматики | PneumoScheme/Mnemo page | Вкладка preview внутри «Исходных данных» и отдельный документ/панель в «Аниматоре» | `поиск: мнемосхема / пневматика / клапан / ресивер` | Синхронное графическое представление вместе с полями ввода и выбором узлов. |
| `WEB-013` Диагностика и SEND bundle | Diagnostics / Hub / send_results_gui | Рабочее пространство «Диагностика» + заметная глобальная кнопка | `поиск: диагностика / собрать диагностику / health report` | Одна заметная кнопка, видимый состав архива, self-check, путь к последнему архиву. |
| `WEB-014` Параметры приложения и инструменты | Settings / tools scattered pages | Рабочее пространство «Параметры и инструменты» + меню приложения | `поиск: параметры / настройки / инструменты / selfcheck` | Служебное убрано с первого плана, но доступно через поиск и меню приложения. |
| `WEB-015` Справочник параметров, единицы, help | Help pages / units pages / tooltips | Правый инспектор «Справка» + знак вопроса + поиск команд | `поиск: помощь / единицы / справочник параметров` | Каждый элемент имеет tooltip и развёрнутое описание, без скрытых legacy-help маршрутов. |
| `WEB-016` Поиск команд | Ранее отсутствовал как единый first-class слой | Верхняя командная панель | `поиск сам является входом` | Находит команды, параметры, тесты, сценарии, run и артефакты. |
| `WEB-017` Артефакты и export files | Разрозненные ссылки на CSV/JSON/NPZ | Левое дерево истории и вкладка «Артефакты» в анализе/диагностике | `поиск: артефакты / CSV / NPZ / JSON` | Явная привязка артефакта к run, stage и objective contract. |
| `WEB-018` Preflight / selfcheck / целостность схемы | Preflight и отдельные check pages | Раздел «Проверка» в правом инспекторе и экран «Диагностика» | `поиск: selfcheck / preflight / целостность схемы` | Связь с конкретным полем или run, а не абстрактный отчёт без контекста. |

## Что ещё в разработке

- `WEB-016` остаётся новым обязательным слоем: command search уже входит в
  канон, но дальше должен быть доведён до полного element-level coverage по
  `ui_element_catalog.csv`, `help_catalog.csv` и `tooltip_catalog.csv`.
- `source_of_truth_matrix.csv`, `keyboard_matrix.csv`, `docking_matrix.csv`,
  `ui_state_matrix.csv` и `pipeline_observability.csv` теперь считаются
  обязательными уточняющими слоями поверх migration/parity contract.
- Hosted desktop shell должен постепенно убрать legacy bridges там, где уже
  существуют spec-compliant native workspaces.

## Специализированное уточнение для `WS-RING`

Общий parity-layer остаётся привязан к `v3`, но для ring editor действует
дополнительный специализированный addendum:

- [pneumo_gui_codex_spec_v13_ring_editor_migration.json](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/pneumo_gui_codex_spec_v13_ring_editor_migration.json)
- [web_to_desktop_migration_matrix_v13.csv](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/web_to_desktop_migration_matrix_v13.csv)
- [ring_editor_schema_contract_v13.json](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json)
- [ring_to_suite_link_contract_v13.json](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json)
- [ring_editor_acceptance_gates_v13.csv](/Users/User/Desktop/pneumo2_R31CN_HF8_github_push_package/pneumo2_R31CN_HF8_repo_root/docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_acceptance_gates_v13.csv)

Этот слой уточняет, что:

- `WS-RING` — единственный пользовательский источник истины для `ring_scenario`;
- поля сегмента редактируются через глобальный правый инспектор, а не через
  локальные скрытые формы;
- `WS-SUITE` хранит только ссылку на канонический экспорт и test-level overrides;
- stale link между экспортом кольца и тестом должен быть видимым предупреждением.

## Как использовать этот summary

- если нужна точная машинная проверка — читать `migration_matrix.csv` и
  `desktop_web_parity_map.json`;
- если нужен проектный смысл и приоритет — читать `17` и `18`;
- если нужно быстро понять маршрут пользователя — начинать с этого summary.
