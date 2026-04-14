# Журнал планов, сгенерированных чатами проекта

> Этот файл обновляется через `pneumo_solver_ui.tools.knowledge_base_sync`.

## Назначение

Этот файл фиксирует планы, decomposition-пакеты, migration-планы и prompt-наборы, которые были сгенерированы в чатах проекта и должны учитываться как рабочий knowledge-base слой.

## Правило ведения

- если чат генерирует рабочий план, migration-map, prompt-pack или ownership matrix, он должен попасть в этот журнал;
- здесь хранится не полный текст каждого плана, а карта plan-артефактов и их назначение;
- полный текст должен лежать в отдельном файле, а здесь должна быть ссылка на него и краткое описание;
- более новый план не стирает старый автоматически: сначала нужно понять, заменяет ли он его или дополняет.

## Актуальные plan-артефакты

1. GUI_MIGRATION_CHAT_PROMPTS.md
Назначение: GUI-only пакет миграции из WEB в desktop GUI по отдельным направлениям.
Артефакт: [GUI_MIGRATION_CHAT_PROMPTS.md](./GUI_MIGRATION_CHAT_PROMPTS.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0001`.

2. PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md
Назначение: Исторический пакет параллельной разработки GUI и WEB. После решения о GUI-first WEB-часть использовать только как reference.
Артефакт: [PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md](./PARALLEL_CHAT_PROMPTS_GUI_AND_WEB_2026-04-12.md)
Статус: частично актуален.
Источник: chat.
ID: `PLAN-0002`.

3. gui_chat_prompts/00_INDEX.md
Назначение: Индекс prompt-файлов для параллельных GUI-чатов.
Артефакт: [gui_chat_prompts/00_INDEX.md](./gui_chat_prompts/00_INDEX.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0003`.

4. gui_chat_prompts/01_MAIN_WINDOW.md
Назначение: Главное окно приложения.
Артефакт: [gui_chat_prompts/01_MAIN_WINDOW.md](./gui_chat_prompts/01_MAIN_WINDOW.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0004`.

5. gui_chat_prompts/02_INPUT_DATA.md
Назначение: Ввод исходных данных.
Артефакт: [gui_chat_prompts/02_INPUT_DATA.md](./gui_chat_prompts/02_INPUT_DATA.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0005`.

6. gui_chat_prompts/03_RUN_SETUP.md
Назначение: Настройка расчёта.
Артефакт: [gui_chat_prompts/03_RUN_SETUP.md](./gui_chat_prompts/03_RUN_SETUP.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0006`.

7. gui_chat_prompts/04_RING_EDITOR.md
Назначение: Редактор и генератор сценариев колец.
Артефакт: [gui_chat_prompts/04_RING_EDITOR.md](./gui_chat_prompts/04_RING_EDITOR.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0007`.

8. gui_chat_prompts/05_COMPARE_VIEWER.md
Назначение: Compare viewer.
Артефакт: [gui_chat_prompts/05_COMPARE_VIEWER.md](./gui_chat_prompts/05_COMPARE_VIEWER.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0008`.

9. gui_chat_prompts/06_DESKTOP_MNEMO.md
Назначение: Desktop mnemo.
Артефакт: [gui_chat_prompts/06_DESKTOP_MNEMO.md](./gui_chat_prompts/06_DESKTOP_MNEMO.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0009`.

10. gui_chat_prompts/07_DESKTOP_ANIMATOR.md
Назначение: Desktop animator.
Артефакт: [gui_chat_prompts/07_DESKTOP_ANIMATOR.md](./gui_chat_prompts/07_DESKTOP_ANIMATOR.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0010`.

11. gui_chat_prompts/08_OPTIMIZER_CENTER.md
Назначение: Optimizer center со всеми настройками.
Артефакт: [gui_chat_prompts/08_OPTIMIZER_CENTER.md](./gui_chat_prompts/08_OPTIMIZER_CENTER.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0011`.

12. gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md
Назначение: Diagnostics и send bundle.
Артефакт: [gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md](./gui_chat_prompts/09_DIAGNOSTICS_SEND_BUNDLE.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0012`.

13. gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md
Назначение: Test, validation, results center.
Артефакт: [gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md](./gui_chat_prompts/10_TEST_VALIDATION_RESULTS.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0013`.

14. gui_chat_prompts/11_GEOMETRY_REFERENCE.md
Назначение: Geometry, catalogs, reference.
Артефакт: [gui_chat_prompts/11_GEOMETRY_REFERENCE.md](./gui_chat_prompts/11_GEOMETRY_REFERENCE.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0014`.

15. gui_chat_prompts/12_ENGINEERING_ANALYSIS.md
Назначение: Engineering analysis, calibration, influence.
Артефакт: [gui_chat_prompts/12_ENGINEERING_ANALYSIS.md](./gui_chat_prompts/12_ENGINEERING_ANALYSIS.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0015`.

16. 17_WINDOWS_DESKTOP_CAD_GUI_CANON.md
Назначение: Project-wide Windows desktop CAD/CAM/CAE GUI canon для shell, editor-окон, viewport/workspace-поверхностей и analysis-модулей.
Артефакт: [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](./17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0016`.

17. 18_PNEUMOAPP_WINDOWS_GUI_SPEC.md
Назначение: Decision-complete GUI-spec для shell, workspaces, command model, workflows, diagnostics, animator truth policy и acceptance criteria проекта Пневмоподвеска.
Артефакт: [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0017`.

18. 18_PNEUMOAPP_WINDOWS_GUI_SPEC.md (augmented A–M revision)
Назначение: Revision existing project-specific GUI spec to augmented A–M contract with optimization transparency, ring-editor source-of-truth, diagnostics operational surface, truthful animator policy, status/taskbar policy and DPI/windowing/performance rules.
Артефакт: [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0018`.

19. Refined GUI-spec synchronization from deep research
Назначение: Уточнить 17-й canon, 18-й project-specific GUI-spec, prompt-layer и knowledge-base summary по deep-research-report.md без изменения runtime GUI и без потери web-to-desktop functional parity.
Артефакт: [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
Статус: актуален.
Источник: chat.
ID: `PLAN-0019`.

## Текущее правило интерпретации

Если в будущем возникает вопрос:

- "какой план у проекта сейчас?",
- "какой prompt выдавать новому чату?",
- "какая декомпозиция уже была согласована?",

то сначала нужно читать этот файл, затем открывать соответствующий linked plan document.

