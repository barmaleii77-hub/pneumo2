# Human GUI Report-Only V15: state continuity and repair loops

Источник: `C:/Users/User/Downloads/pneumo_human_gui_report_only_v15_state_continuity_repair_loops.zip`.

Дата внесения в KB: 2026-04-21.

## Статус

V15 является report-only слоем без кода, без runtime acceptance и без runtime-closure proof. Архив прочитан и сохранён как repo-local reference layer:
`docs/context/gui_spec_imports/v15_state_continuity_repair_loops/`.

Слой не заменяет `17/18`, `v38_actualized_with_v10`, `v19_graph_iteration` или `v12_window_internal_routes`. Он добавляет поверх них отдельный контракт state continuity: пользователь должен понимать текущий контекст, доверенность состояния, причину stale/dirty/mismatch/degraded и единственный основной repair-route.

## Прочитанные файлы архива

- `EXEC_SUMMARY.md`
- `STATE_CONTINUITY_AND_REPAIR_LOOP_CONTRACT_V15.md`
- `WINDOW_STATE_MARKER_MATRIX_V15.csv`
- `REPAIR_LOOP_POLICY_V15.csv`
- `STALE_DIRTY_MISMATCH_TRUTH_MATRIX_V15.csv`
- `CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv`
- `WINDOW_ENTRY_POLICY_V15.csv`
- `COGNITIVE_MUST_SEE_MARKERS_V15.csv`
- `COGNITIVE_BREAKPOINTS_V15.csv`
- `ACTION_CONFIRMATION_AND_RESULT_VISIBILITY_V15.csv`
- `ENTRY_STATE_REPAIR_GRAPH_V15.dot`
- `WHAT_IS_GOOD_V15.md`
- `WHAT_IS_BAD_V15.md`
- `HOW_TO_FIX_V15.md`
- `LIMITS_AND_EVIDENCE_V15.md`
- `PACKAGE_MANIFEST.json`

## Главный вывод

Проблема GUI уже не только в том, открывается ли нужная поверхность напрямую. После открытия пользователь должен сразу видеть:

- какой контекст открыт сейчас;
- можно ли доверять текущему состоянию;
- что именно несохранено, устарело, не совпадает или работает в degraded mode;
- какая одна основная repair-action починит состояние;
- куда система вернёт пользователя после repair-route.

## Требования, добавленные в KB

1. Каждый primary workspace обязан иметь видимые state markers для `dirty`, `invalid`, `stale`, `mismatch` и `degraded`, если такое состояние применимо к workspace.
2. У каждого проблемного состояния должен быть один основной repair-action и один ожидаемый resolved-state.
3. Repair-action должен вести в upstream workspace напрямую: stale suite возвращает в `WS-RING`, baseline mismatch возвращает в `WS-BASELINE`, objective mismatch возвращает в `WS-OPTIMIZATION`, stale bundle возвращает в `WS-DIAGNOSTICS`.
4. При handoff/repair-return нужно сохранять selection, focus, compare/overlay context и scroll там, где это указано в `CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv`.
5. Исторический/current context должен быть видимым banner/card, чтобы пользователь не путал live state с archived run.
6. Degraded truth не маскируется под нормальный режим: должен быть warning strip, provenance и ограниченный набор действий.

## Границы доказательности

V15 не доказывает, что текущие окна уже визуально реализуют эти repair loops. Это reference-layer для следующих GUI-доработок и contract-tests. Runtime closure требует отдельного evidence layer: screenshots/visual smoke, state-transition tests and command-route checks.
