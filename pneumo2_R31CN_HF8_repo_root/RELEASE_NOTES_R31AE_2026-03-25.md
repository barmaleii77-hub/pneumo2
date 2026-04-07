# Release notes — R31AE (2026-03-25)

`PneumoApp_v6_80_R176_R31AE_2026-03-25`

## Scope

R31AE is a focused follow-up over R31AD. This pass implements the four targeted fixes requested after the latest visual review:

- restore normal scenario selection UX without auto-running enabled defaults;
- harden Web UI idle CPU behavior so paused/hidden followers wake mainly from events, not tight polling;
- move road surface and visible wire grid onto stable native support rows instead of frame-local visible-window resampling;
- make cylinders easier to read by adding explicit frame-mount markers and reducing the visual dominance of the full housing shell.

## Included fixes

### 1) Scenario selection UX

- Removed the forced fresh-session `(не выбрано)` policy from the main suite editor.
- Main and legacy suite editors now return to normal selection behavior: the first row is selected for editing when a suite exists.
- Both shipped default suites now start with **all scenarios disabled** by default, so a fresh baseline page no longer silently runs an enabled scenario from the preset.
- Manual ring-scenario creation still starts with `"включен": True`, matching the request that a newly created scenario should be immediately editable/runnable on purpose.

### 2) Web UI idle CPU

- Browser follower components and embedded HTML widgets now use a much stricter idle cadence:
  - old paused-idle wakeups at ~3.5–5.0 s were removed;
  - idle cadence is now `15 s / 30 s / 60 s`.
- The existing single-flight / visibility-aware wake path remains in place, so `storage`, `focus` and `visibility` events become the main wake triggers instead of frequent timeout polling.

### 3) Road drift

- Dense road surface already had a stable spacing policy, but R31AE goes one step further: both surface rows and visible wire-grid crossbars now come from **stable native support rows** anchored to dataset `s_world`.
- The frame-local visible-window resampling path is kept only as a conservative fallback, not as the primary geometry source.
- This is aimed specifically at the resize/playback-dependent drift the user still observed after earlier grid-only fixes.

### 4) Cylinder readability and frame mount markers

- Added explicit frame-mount markers for cylinder frame-side points (`cyl*_top`) so the axis placement can be inspected visually.
- Reduced housing-shell visual dominance by weakening shell edge alpha and switching the shell to translucent rendering.
- Strengthened chamber / piston readability so the internals are easier to distinguish from the shell and rod.

## Validation

- `py_compile`: PASS
- `compileall`: PASS
- targeted regression pytest slice: 40 passed

## Remaining live acceptance

A fresh Windows SEND bundle is still required to prove R31AE on the real stack:

- idle CPU after calculations must stay quiet in the browser/Web UI path;
- road surface and wire grid must stay visually locked to the road during playback and resize;
- cylinder frame markers must match the expected frame-side mounting points;
- scenario list must keep normal selection while shipped presets remain disabled by default.
