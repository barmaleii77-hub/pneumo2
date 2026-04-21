# V15 state continuity and repair loops

Источник: `C:/Users/User/Downloads/pneumo_human_gui_report_only_v15_state_continuity_repair_loops.zip`.

Дата импорта в KB: 2026-04-21.

## Роль слоя

Этот каталог хранит report-only слой V15 про непрерывность состояния, stale/dirty/mismatch/degraded состояния и repair-loop маршруты. Слой не содержит runtime/UI-кода и не является runtime-closure proof.

V15 продолжает текущую ветку GUI knowledge stack после `v38_actualized_with_v10`, `v19_graph_iteration` и `v12_window_internal_routes`: V19 уточняет action-feedback на выбранных рабочих пространствах, V12 уточняет первый экран и внутренние маршруты отдельных окон, а V15 добавляет общий контракт восстановления состояния и возврата пользователя в правильную upstream-точку без потери контекста.

## Как применять

Использовать V15, когда работа касается:

- сохранения/восстановления выбранного проекта, run, scenario, baseline, compare context, plot, animator truth state или diagnostics bundle;
- пользовательских состояний `dirty`, `invalid`, `stale`, `mismatch`, `degraded`;
- repair-action, который должен вести в один основной upstream workspace, а не в конкурирующие окна;
- видимых marker/banner/card состояний, которые объясняют, что устарело, что сломано и что делать дальше;
- возврата после repair-route в тот же участок pipeline, а не на пустой стартовый экран.

## Файлы пакета

- `STATE_CONTINUITY_AND_REPAIR_LOOP_CONTRACT_V15.md` - основной human-readable контракт.
- `WINDOW_STATE_MARKER_MATRIX_V15.csv` - state -> marker/action/return-target matrix.
- `REPAIR_LOOP_POLICY_V15.csv` - state trigger -> feedback -> repair action -> resolved state.
- `STALE_DIRTY_MISMATCH_TRUTH_MATRIX_V15.csv` - source-of-truth matrix for stale/dirty/mismatch/degraded states.
- `CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv` - handoff/repair return target and selection-restore matrix.
- `WINDOW_ENTRY_POLICY_V15.csv` - entry mode, dock contract and inherited context rules.
- `COGNITIVE_MUST_SEE_MARKERS_V15.csv` - user-visible marker requirements.
- `COGNITIVE_BREAKPOINTS_V15.csv` - high-risk cognitive breakpoints and required markers.
- `ACTION_CONFIRMATION_AND_RESULT_VISIBILITY_V15.csv` - action -> feedback -> persistent marker rules.
- `ENTRY_STATE_REPAIR_GRAPH_V15.dot` - graph of state repair transitions.
- `WHAT_IS_GOOD_V15.md`, `WHAT_IS_BAD_V15.md`, `HOW_TO_FIX_V15.md` and `LIMITS_AND_EVIDENCE_V15.md` - short report notes.
- `EXEC_SUMMARY.md` - package summary.
- `PACKAGE_MANIFEST.json` - imported source manifest.

## Evidence boundary

V15 is an imported reference layer. It does not prove that current runtime windows already implement these markers, state transitions or repair routes. Runtime acceptance still requires separate visual/runtime evidence and tests.
