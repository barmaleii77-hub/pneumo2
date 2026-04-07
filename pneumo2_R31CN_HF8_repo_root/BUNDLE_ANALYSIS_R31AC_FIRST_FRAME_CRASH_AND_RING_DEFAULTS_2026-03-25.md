# Bundle analysis — R31AC first-frame crash and ring defaults (2026-03-25)

## What was actually broken

The latest SEND bundle proves that the user symptom "Animator hangs, road not visible" was a **consumer-side first-frame crash**, not missing road data.

Desktop Animator spawned and then failed in:

`load_npz -> _update_frame(0) -> cockpit.update_frame -> car3d.update_frame -> _circle_line_vertices(...)`

The exact exception from bundle logs was:

- `TypeError`
- `TypeError("Car3DWidget._circle_line_vertices() missing 1 required positional argument: 'self'")`

The failure happened while building the piston-ring line layer, so the whole first frame aborted before the road scene could finish painting.

## Why the road still matters here

The bundle still contained the required export assets:

- `anim_latest.npz`: **present**
- `anim_latest.json`: **present**
- `anim_latest_road_csv.csv`: **present**

So the road was not absent; the scene consumer crashed before the road became visible.

## Fix applied in R31AD

1. `Car3DWidget._circle_line_vertices` now has a valid staticmethod signature (no stray `self` positional arg).
2. Piston-ring polyline rendering is now fail-soft: if this sublayer breaks again, the ring is hidden and logged instead of aborting the whole frame.
3. Ring editor defaults were synchronized to the latest user-approved ring setup extracted from `anim_latest_scenario_json.json`.
4. The suite scenario list now allows an explicit `(не выбрано)` state instead of auto-selecting the first row.

## Ring defaults adopted

Top-level defaults now follow the exported ring scenario:

- `closure_policy = closed_c1_periodic`
- `v0_kph = 40.0`
- `seed = 123`
- `dx_m = 0.02`
- `n_laps = 1`

Key segment defaults now match the last user setup:

- `S1_прямо`: `ISO8608 / class E / seed 12345`
- `S2_поворот`: `SINE / A_L=A_R=50 mm / λ_L=λ_R=1.5 m / phaseR=180° / random phase toggles on`
- `S3_разгон`: `ISO8608 / class E / seed 54321`
- `S4_торможение`: `ISO8608 / class E / seed 999`

## Expected result after R31AD

A fresh Windows SEND bundle should now show:

- Desktop Animator opens without `TypeError` on `_circle_line_vertices`;
- road is visible from the first frame;
- ring editor starts from the new default setup;
- the suite list starts with no selected scenario until the user picks one explicitly.
