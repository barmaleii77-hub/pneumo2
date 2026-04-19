# Human GUI Simulation Audit V5: module-internals pass

Source archive: `C:/Users/Admin/Downloads/pneumo_human_gui_simulation_audit_v5_module_internals.zip`

Import date: 2026-04-19

## Role In Knowledge Base

This V5 package is an evidence-first UX audit layer. It does not replace V38 GUI/TZ/spec canon and does not close runtime acceptance by itself.

Use it to keep future GUI work honest about what is actually known:

- `launchpoint_only`: only a button or entry point is confirmed.
- `launchpoint_plus_prelaunch`: the entry point and pre-launch explanation are confirmed.
- `source_contract_opened`: internal meaning is supported by source/release evidence, but live layout is not fully proven.
- `runtime_opened`: the live surface behavior/content has been opened and checked.

## Files Read From Archive

- `README.md`
- `USER_JOURNEY_SIMULATION_V5.md`
- `NEXT_FIXES_V5.md`
- `QUESTIONS_AND_GAPS_V5.md`
- `WINDOW_MODULE_INTERNALS_V5.csv`
- `WINDOW_INTERNALS_MATRIX_V5.csv`
- `CONFUSION_AND_GAPS_V5.csv`
- `OPENED_SURFACES_V5.csv`
- `WINDOW_EVIDENCE_LEVELS_V5.csv`
- `MANIFEST.json`

## Main Findings

1. The current problem is no longer missing launch buttons. The problem is too many parallel entry points without clear hierarchy.
2. Desktop Animator is currently the best explained surface: follow workflow, pointer path, readiness, road preview, playback cadence, pointer watcher, cylinder truth gate and degraded axis-only mode have evidence.
3. Desktop Mnemo is confirmed as a related launch/follow surface, but its internal layout and user explanation are still weak.
4. Compare exists both as embedded comparison and as a separate Compare Viewer. Their user-facing difference must be explicit.
5. Diagnostics has strong subsystem evidence (`health_report`, `make_send_bundle`, `selfcheck_suite`, workspace checks, latest send bundle and helper runtime provenance), but the user route must be dominated by one clear action: `Собрать диагностику`.
6. GUI отправки результатов is adjacent to diagnostics and should not confuse the operator with a second equivalent route.
7. Редактор исходных данных and Центр тестов are canonically important, but V5 treats their live internals as under-proven until source/runtime evidence is collected.
8. Центр desktop-инструментов has the weakest user role and should not be presented as an equal primary workspace without a clearer purpose.

## Required Remediation Direction

1. Build a launcher hierarchy: primary workspaces first, auxiliary/specialized windows second.
2. Keep diagnostics and send-results internals separate in code, but expose one dominant user path: `Собрать диагностику`.
3. Explain when embedded compare is enough and when the separate Compare Viewer is needed.
4. Add pre-launch cards/status for Desktop Mnemo, Diagnostics, Compare Viewer, Input Editor and Test Center, similar in clarity to Desktop Animator.
5. Use evidence-first language: do not claim a window is fully understood unless its layout/behavior was actually opened or proved by source/runtime evidence.

## Next Evidence Priorities

1. GUI диагностики
2. Compare Viewer
3. Desktop Mnemo
4. Редактор исходных данных
5. Центр тестов
6. Центр desktop-инструментов

## Non-Contradiction With Current Canon

V38 remains the current GUI/TZ/spec imported reference. V5 narrows acceptance discipline: it says which GUI windows are still under-proven by evidence and how to prioritize the next remediation pass.

No V5 statement allows service jargon, hidden migration status, raw technical keys, duplicate ownership of Animator/Mnemo/Compare, or WEB-first development.
