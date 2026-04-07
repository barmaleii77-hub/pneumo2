# Bundle analysis — R31AB animator crash (2026-03-25)

## Bundle under analysis
- Release: `PneumoApp_v6_80_R176_R31AB_2026-03-25`
- ZIP: `SEND_20260325_092217_auto-sys.excepthook_bundle.zip`
- Created: `2026-03-25T09:22:21`

## What the bundle proves
This was **not** a missing-road / broken-export case.
The bundle contains a healthy `anim_latest` set:
- `anim_latest.npz` present
- `anim_latest.json` present
- `anim_latest_road_csv.csv` present
- pointer sync = `OK`
- geometry acceptance = `PASS`
- validation / health report = `OK`

## Real root cause
Desktop Animator crashed on first-frame load with:

`TypeError: Car3DWidget._corner_is_front() takes 1 positional argument but 2 were given`

Crash path from the bundle event log:
`load_npz -> _update_frame(0) -> cockpit.update_frame -> car3d.update_frame -> _corner_cylinder_contract -> _corner_is_front`

So the user-facing symptom “аниматор висит, дороги не видно” came from a **consumer-side crash during scene update**, not from absent road data.

## Fix applied in R31AC
- restored explicit helper semantics for `Car3DWidget._corner_is_front` via `@staticmethod`
- kept the existing call-site `self._corner_is_front(corner)` valid
- added a regression test that fails if the helper loses its binding semantics again

## Expected result after R31AC
- Desktop Animator should no longer die on the first frame
- road should become visible because scene painting is allowed to complete
- future SEND bundles should no longer contain `sys.excepthook` / `TypeError` for `_corner_is_front`
