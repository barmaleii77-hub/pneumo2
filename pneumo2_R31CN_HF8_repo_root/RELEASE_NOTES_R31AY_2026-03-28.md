# Release notes — R31AY (2026-03-28)

## What changed

- Centralized run/output/test-name sanitization into `pneumo_solver_ui/name_sanitize.py`.
- Preserved readable Unicode names on Windows while hardening against forbidden path characters and reserved basenames such as `CON`, `PRN` and `LPT1`.
- Removed duplicated local `sanitize_id` / `_sanitize_id` / `sanitize_test_name` implementations from `app.py`, `pneumo_ui_app.py` and `opt_stage_runner_v1.py`.
- Added regression tests so this optimization/runtime hot path cannot drift silently again.

## Why this matters

The previous optimization page crash was a symptom of sanitizer drift between UI entrypoints. R31AY removes that drift by giving all three runtime entrypoints one shared helper and one shared Windows-safe contract.
