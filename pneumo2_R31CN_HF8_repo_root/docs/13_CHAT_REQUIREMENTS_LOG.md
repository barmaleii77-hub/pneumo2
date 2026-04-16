# Журнал требований из чатов проекта

> Этот файл обновляется через `pneumo_solver_ui.tools.knowledge_base_sync`.

## Назначение

Этот файл фиксирует пользовательские хотелки, решения и рабочие директивы, которые были сформулированы в чатах проекта и должны сохраняться для последующего использования.

Это не канон уровня `ABSOLUTE LAW`, но это обязательный knowledge-base слой рабочего контекста.

## Правило ведения

- добавлять сюда каждую существенную пользовательскую хотелку из чатов проекта;
- писать кратко, но однозначно;
- если требование потом реализовано, не удалять его, а отмечать статус;
- если требование конфликтует с каноном, канон важнее, но конфликт должен быть явно отмечен.

## Активные требования, уже зафиксированные в чатах

1. Проект должен мигрировать из WEB в понятный классический desktop GUI под Windows без потери функциональности.
Статус: активно.
Источник: chat.
ID: `REQ-0001`.

2. WEB больше не является целевой платформой развития пользовательских сценариев.
В WEB допустимы только минимальные мосты, launch-кнопки и reference-поведение до полного переноса в GUI.
Статус: активно.
Источник: chat.
ID: `REQ-0002`.

3. Главные операторские сценарии должны жить в GUI.
Состав: главное окно приложения; ввод исходных данных; настройка расчёта; редактор и генератор сценариев колец; compare viewer; desktop mnemo; desktop animator; optimizer center; diagnostics/send bundle; validation/results/test center; geometry/reference center; engineering analysis/calibration/influence.
Статус: активно.
Источник: chat.
ID: `REQ-0003`.

4. Архитектура GUI должна быть модульной и пригодной для параллельной разработки разными чатами без пересечения по тем же файлам.
Статус: активно.
Источник: chat.
ID: `REQ-0004`.

5. Нельзя дублировать домены Desktop Animator, Compare Viewer и Desktop Mnemo в других окнах без отдельной необходимости.
Статус: активно.
Источник: chat.
ID: `REQ-0005`.

6. Главное desktop-приложение должно быть классическим Windows GUI с верхним меню и многооконным интерфейсом внутри приложения.
Статус: активно.
Источник: chat.
ID: `REQ-0006`.

7. Ввод исходных данных должен быть удобным, секционным и понятным для пользователя.
Минимальные кластеры: геометрия; пневматика; механика; настройки расчёта.
Статус: активно.
Источник: chat.
ID: `REQ-0007`.

8. Все пользовательские хотелки из чатов этого проекта должны записываться в базу знаний.
Статус: активно.
Источник: chat.
ID: `REQ-0008`.

9. Все планы работ, prompt-пакеты и decomposition, которые генерируют чаты этого проекта, должны записываться в базу знаний.
Статус: активно.
Источник: chat.
ID: `REQ-0009`.

10. База знаний должна автоматически обновляться и сохраняться локально и в удалённом репозитории.
Для chat-capture используется knowledge_base_sync: запись в JSON store, перегенерация markdown-журналов и по умолчанию stage/commit/push в текущую ветку.
Статус: активно.
Источник: chat.
ID: `REQ-0010`.

11. Проект должен использовать отдельный Windows desktop CAD/CAM/CAE GUI canon как главный baseline для всего desktop suite.
Baseline: menu bar + toolbar + dockable/floating/auto-hide panes + command search + status/progress strip; ribbon допустим только как отдельно обоснованное исключение для конкретного workspace.
Статус: активно.
Источник: chat.
ID: `REQ-0011`.

12. Проект должен использовать project-specific Windows desktop GUI-spec для PneumoApp поверх общего CAD GUI canon.
Spec фиксирует 4 workspace-группы, global diagnostics action, один selector optimization-mode, first-class Test Suite/Scenario generation, honest animator truth states и source-of-truth map для setup, suite, baseline, optimization и analysis.
Статус: активно.
Источник: chat.
ID: `REQ-0012`.

13. Проект должен использовать augmented A–M Windows desktop GUI contract для PneumoApp поверх общего CAD GUI canon.
Contract фиксирует workflow-first IA, ring editor как единственный source-of-truth сценариев, один active optimization mode, first-class diagnostics, honest animator truth states, taskbar/status/progress policy и snap/DPI/performance discipline.
Статус: активно.
Источник: chat.
ID: `REQ-0013`.

14. Refined GUI-spec для desktop migration должен опираться на deep research по Windows windowing, tooltip/help, truthful graphics и измеримому DPI/performance behavior.
Уточнённый GUI-spec обязан явно фиксировать native Windows title-bar/system-menu/snap behavior, tooltip и question-mark help contract, source markers и время построения для графических представлений, а также проверяемые требования по Per-Monitor V2, WM_DPICHANGED, UI Automation, idle CPU, hidden panes, taskbar progress и ETW-style instrumentation.
Статус: активно.
Источник: chat.
ID: `REQ-0014`.

15. Connector-reconciled GUI/TZ spec v32 is an active knowledge-base reference
Archive C:/Users/Admin/Downloads/pneumo_codex_tz_spec_connector_reconciled_v32.zip refines the GUI-first migration knowledge base with source authority, reading order, 12 workspace contracts, 45 requirements, 45 acceptance rows, acceptance playbooks, release gates, runtime artifact schema, evidence policy and open gaps. It informs future GUI/TZ work but does not override 00 law, parameter registry, unified data contract or human-readable canon docs 17/18.
Статус: активно.
Источник: chat + archive:pneumo_codex_tz_spec_connector_reconciled_v32.
ID: `REQ-0015`.

16. Before using v32 as an implementation guide, check completeness and runtime limits
The connector-reconciled v32 package is sufficient as a planning, contract, source-authority, workspace/handoff and acceptance/evidence layer, but it is not runtime closure proof. Future chats must consult COMPLETENESS_ASSESSMENT.md and must not claim producer truth, cylinder packaging, measured performance, Windows visual acceptance or imported-layer runtime closure without fresh tests/artifacts/SEND bundle evidence.
Статус: активно.
Источник: chat + v32 completeness assessment.
ID: `REQ-0016`.

## Как ссылаться из будущих задач

Если новая задача опирается на решение из чата, но не отражена в старом каноне, сначала проверить этот файл, а затем соответствующие plan-файлы из [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md).

