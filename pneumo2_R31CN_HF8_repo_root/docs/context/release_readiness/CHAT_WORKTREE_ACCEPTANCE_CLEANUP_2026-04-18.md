# Chat Worktree Acceptance Cleanup 2026-04-18

## Назначение

Этот документ фиксирует интеграционную приемку локальных chat-worktree после
V38 GUI-цикла. Он нужен, чтобы будущие чаты не поднимали старые временные
ветки как рабочий источник и не повторяли уже принятые изменения.

## Принятые источники

В `codex/work` перенесены полезные изменения из локальных рабочих деревьев:

- `pneumo2_compare_viewer_selected_runs_audit`
- `pneumo2_desktop_animator_v38_provenance_status`
- `pneumo2_diagnostics_send_bundle_open_gaps`
- `pneumo2_engineering_analysis_center_hardening`
- `pneumo2_geometry_reference_open_gap_audit`
- `pneumo2_input_v38_audit`
- `pneumo2_main_window_navigation_audit`

Отдельные локальные ветки `codex/desktop-mnemo-visual-labels` и
`codex/scenarios-ring-run-setup-v38-audit-20260418` учтены через уже
существующие dirty-изменения основного дерева.

## Не принятые как source-of-truth артефакты

Сгенерированные runtime/report артефакты из временных рабочих деревьев не
считаются каноном и не переносятся как кодовый baseline:

- `REPORTS/SELF_CHECK...`
- временные `diagnostics/` output-каталоги
- любые локальные ZIP/JSON, созданные как результат запуска инструментов

Такие файлы могут использоваться только как одноразовая подсказка, но не как
основание для закрытия release-gate без воспроизводимого runtime evidence.

## Интеграционные правила после уборки

- Новые GUI-чаты стартуют только от clean `origin/codex/work`.
- Старые chat-worktree и локальные chat-ветки являются историей и подлежат
  удалению после успешного интеграционного коммита.
- Нельзя заново cherry-pick/merge старые ветки без отдельной сверки с текущим
  `codex/work`.
- Нельзя закрывать open gaps только потому, что тестовый контракт прошел.
- Любая пользовательская поверхность должна быть на русском и без служебных
  формулировок вроде `Статус миграции`, `Открыть выбранный этап`,
  `Данные машины`, raw runtime/toolkit labels или английских status strings.

## Принятые функциональные направления

- главное окно, навигация и V38 pipeline surfaces;
- ввод исходных данных, настройка расчета и снимки handoff;
- редактор/генератор сценариев кольца и подготовка прогона;
- Compare Viewer selected-runs/session context;
- Desktop Mnemo visual labels and launcher contract;
- Desktop Animator operator text, context and provenance;
- optimizer/results/test flow;
- Diagnostics/SEND bundle with visible progress and honest open gaps;
- Geometry/Catalogs/Reference producer evidence;
- Engineering Analysis/Calibration/Influence evidence.

## Проверки приемки

На момент фиксации приемки выполнен focused pytest по затронутым GUI-направлениям
и encoding/mojibake contract. Финальный интеграционный коммит должен повторно
проверить:

- `git diff --check`
- focused pytest по затронутым lanes;
- `python -m pytest tests/test_ui_text_no_mojibake_contract.py -q`;
- отсутствие служебных/английских operator-facing строк в измененных GUI;
- синхронизацию `codex/work` с `origin/codex/work`.

## Связанные промты

Текущий пакет стартовых промтов для следующих параллельных чатов:

- `docs/gui_chat_prompts/18_POST_CHAT_WORKTREE_CLEANUP_V38_PLAN_MODE_PROMPTS.md`
