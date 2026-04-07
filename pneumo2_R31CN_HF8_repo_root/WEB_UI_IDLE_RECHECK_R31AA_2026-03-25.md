# Web UI idle CPU recheck — R31AA (2026-03-25)

## Summary
This pass rechecked the user claim that the **idle CPU source is the Web UI**.
The new work therefore focused on browser followers and inline HTML widgets instead of mixing in unrelated geometry/Qt changes.

## Root causes identified by code audit

### A. Hidden tabs were still treated as visible
The shared iframe visibility helper only checked viewport coordinates.
That misses the common Streamlit case where a hidden/collapsed tab keeps an iframe element in the DOM but with effectively zero size.

### B. Some high-cost widgets could run more than one loop chain
The wake paths in `mech_anim`, `mech_car3d`, and `pneumo_svg_flow` did not always cancel already scheduled RAF/timeout work before starting a new wake cycle.
That means browser CPU could remain elevated after a detail-run even when nothing meaningful was changing on screen.

## Implemented mitigation
- Hardened iframe off-screen detection.
- Slower paused idle polls.
- Single-flight schedulers for the heaviest browser loops.
- Same off-screen policy also applied to inline HTML widgets in `app.py` / `pneumo_ui_app.py`.

## What this report does not claim
This report does **not** claim measured Windows acceptance.
It documents a code-level fix path and the reasoning behind the patch.
A new SEND bundle is still required for live confirmation.
