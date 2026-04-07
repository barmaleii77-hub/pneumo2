# Release notes — R31AC (2026-03-25)

## Release
`PneumoApp_v6_80_R176_R31AC_2026-03-25`

## What this patch targets
This patch deliberately targets the **new Desktop Animator startup regression** found in the latest Windows SEND bundle.
It does **not** mix another round of browser idle / road rendering / cylinder visual redesign into the same release.

## Bundle-driven diagnosis
Latest bundle signals were internally consistent:
- send bundle validation = OK
- health report = OK
- geometry acceptance = PASS
- `anim_latest.npz` present
- `anim_latest_road_csv.csv` present
- pointer sync = OK

Despite that, Desktop Animator died on startup with:
- `TypeError: Car3DWidget._corner_is_front() takes 1 positional argument but 2 were given`

That means the symptom “Animator hangs / road is not visible” was caused by a **consumer-side first-frame crash**, not by missing road data.

## What changed

### Desktop Animator crash hotfix
- restored explicit static helper semantics for `Car3DWidget._corner_is_front`
- preserved the existing call pattern `self._corner_is_front(corner)`
- removed the immediate first-frame crash path introduced by the cylinder/packaging pass

### Regression coverage
Added a focused regression test that checks:
- `Car3DWidget._corner_is_front` is either explicitly static or properly bound
- `_corner_cylinder_contract()` still calls the helper through the intended path

## Validation
- `python -m py_compile`: PASS
- `python -m compileall -q .`: PASS
- focused pytest slice: PASS (`22 passed`)
- broader desktop-animator regression slice: PASS (`56 passed`)

## TODO / Wishlist refresh
Updated:
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`

## Still open
- Fresh **Windows SEND bundle** is still required to prove R31AC on the live stack: Animator must open cleanly, road must be visible on the first frame, and no `_corner_is_front` TypeError may appear in bundle logs.
- Web UI idle-CPU acceptance from `R31AB` remains an independent track and was not mixed into this hotfix pass.
