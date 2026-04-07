# RELEASE NOTES — R31BO — 2026-03-30

## Scope
- suite/state/UI pipeline fixes after staged optimization editor audit
- stable selection by canonical suite row id
- suite card draft no longer depends on `st.form(...)`
- reduced explicit full-page reruns in suite actions
- ring scenario generator now targets `ui_suite_selected_id` instead of stale row-index state

## Fixes
- repaired suite editor so draft values persist in Streamlit UI state across ordinary reruns
- repaired suite action buttons (`add/reset/show all/enable/disable/duplicate/delete`) to stop using extra manual reruns where not needed
- preserved visibility for edited/new stage values through the stage filter
- cleared stale legacy `ui_suite_selected_row` state on load and after ring scenario generation
- kept stage normalization / id repair contract tests green

## Verification
- py_compile: PASS
- compileall: PASS
- targeted pytest: PASS (`14 passed`)
