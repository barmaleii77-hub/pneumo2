# Release notes — R31AD (2026-03-25)

`PneumoApp_v6_80_R176_R31AD_2026-03-25`

## Scope

R31AD is a focused hotfix over R31AC. It targets the exact blocker proven by the newest Windows SEND bundle: Desktop Animator crashed on the first frame, so the user saw a hanging animator and no road.

This pass also applies the two UX requests from the same report:

- make the current ring-editor setup the new default;
- make the scenario list start with nothing selected.

## Included fixes

### 1) Desktop Animator first-frame crash

- Fixed `Car3DWidget._circle_line_vertices`: the helper stays `@staticmethod`, but no longer declares a stray `self` positional argument.
- This removes the bundle-proven crash path:
  `load_npz -> _update_frame(0) -> cockpit.update_frame -> car3d.update_frame -> _circle_line_vertices(...)`.

### 2) Fail-soft piston-ring rendering

- Piston-ring line generation is now guarded.
- If a future packaging/visual refactor breaks only the ring polyline, Animator logs the exception and hides that ring instead of aborting the whole frame.

### 3) Ring editor defaults now match the user-approved setup

- `closure_policy = closed_c1_periodic`
- `v0_kph = 40`
- `seed = 123`
- `dx_m = 0.02`
- `n_laps = 1`

Segment defaults now start from the latest exported ring scenario:

- `S1_прямо`: `ISO8608 / E / seed 12345`
- `S2_поворот`: `SINE / A=50 mm / λ=1.5 m / phaseR=180° / random phase toggles enabled`
- `S3_разгон`: `ISO8608 / E / seed 54321`
- `S4_торможение`: `ISO8608 / E / seed 999`

### 4) Scenario list can be explicitly unselected

- Main suite editor (`pneumo_ui_app.py`) now supports `(не выбрано)` in the scenario list.
- A fresh page session clears the suite selection once, instead of auto-selecting the first row.
- Legacy `app.py` suite editor was aligned to the same optional-selection policy.

## Validation

- `py_compile`: PASS
- `compileall`: PASS
- targeted regression pytest slice: 34 passed

## Remaining live acceptance

A fresh Windows SEND bundle is still required to prove R31AD on the real stack:

- Desktop Animator opens without `_circle_line_vertices` TypeError;
- road is visible from the first frame;
- ring editor shows the new defaults;
- scenario list starts with no selected row until the user chooses one.
