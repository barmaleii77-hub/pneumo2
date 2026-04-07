# Bundle analysis — road surface drift + cylinder packaging orientation (2026-03-24)

## What the bundle showed

- The remaining road symptom is no longer only about visible cross-bars.
- In `R31W`, the *dense shaded road surface* was still rebuilt from a fresh per-frame `linspace(s_min, s_max, n_long)`.
- That means the longitudinal triangle rows of the surface mesh changed spacing and phase with the playback window, so users still saw the road mesh drift over the same road relief.

### Measured on the received bundle (representative Desktop Animator view assumptions from current code)

- Dense road surface `ds_long` min: **0.067039 m**
- Dense road surface `ds_long` max: **0.108870 m**
- Unique `ds_long` values across playback: **686**
- `n_long` range during playback: **180 .. 720** (355 unique values)
- Stable bundle/view target spacing chosen for the patch: **0.090094 m**

Interpretation: the wire-grid could already be stabilized, but the shaded surface itself still changed its sampling too much frame-to-frame.

## Cylinder / rod / piston root cause

- The current visual packaging still violated the project context requirement **"цилиндр к раме, шток к рычагу"**.
- Two separate consumer-side problems were present:
  1. the piston stroke direction was interpreted backwards;
  2. the visible cylinder body was rendered along the full `top -> bot` axis, which made the body look anchored on the arm side too.

### Evidence from bundle geometry + stroke traces

- Example actuator: C1 ЛП
  - stroke range: **0.015350 .. 0.231301 m**
  - old implementation: piston fraction vs stroke correlation = **1.000** (wrong sign for this project) 
  - fixed implementation: piston fraction vs stroke correlation = **-1.000**

Interpretation: the old code moved the piston toward the arm / rod-end side as `stroke_pos` grew, while this project defines `stroke_pos` as rod extension. That inverted the visible body/rod semantics.

## Patch direction

- Dense road surface longitudinal rows are now built from a world-anchored, bundle/view-stable spacing instead of a fresh per-frame linspace.
- Cylinder visual law is now explicit: `cyl*_top = frame/body side`, `cyl*_bot = arm/rod side`, `stroke_pos = rod extension`.
- The visible split now reads as:
  - `body = top -> piston_plane`
  - `rod = piston_plane -> bot`
- Piston markers are no longer kept permanently hidden when valid piston centers exist.

## Remaining acceptance task

- A fresh Windows SEND bundle from the patched release is still required to confirm that
  1. the *surface mesh* no longer drifts, not just the cross-bars; and
  2. all cylinders visually read as **body on frame / rod on arm** with visible pistons across the run.
