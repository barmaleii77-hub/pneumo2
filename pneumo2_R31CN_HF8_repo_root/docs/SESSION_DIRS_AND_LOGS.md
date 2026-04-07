# Session dirs, logs and artifacts

The launcher creates a per-run session directory and sets environment variables:

- `PNEUMO_SESSION_DIR`
- `PNEUMO_LOG_DIR`
- `PNEUMO_WORKSPACE_DIR`

## What was fixed in Kod36

Previously, the UI always wrote to local `./pneumo_solver_ui/logs` and `./pneumo_solver_ui/workspace`.
In Kod36, UI resolves directories from env first.

## Expected result

After a run, the session folder contains:
- logs (`logs/`)
- workspace artifacts (`workspace/osc`, `workspace/exports`)
- send-bundle zip (created by send_results_gui)
