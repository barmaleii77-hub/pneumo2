# TODO / Wishlist addendum — R31AD (2026-03-25)

## Closed in this pass

- Fixed the new Desktop Animator first-frame crash from the latest SEND bundle: `Car3DWidget._circle_line_vertices` no longer mixes `@staticmethod` with a stray `self` positional argument.
- Hardened the piston-ring sublayer so it fails soft: ring-line build errors are logged and hidden instead of aborting the whole frame and making the road look missing.
- Promoted the latest ring editor setup to real defaults: `ISO8608/E` straight/accel/brake, `SINE 50 mm / 1.5 m / phaseR=180°` turn segment, `closure_policy=closed_c1_periodic`, `n_laps=1`.
- Updated suite selection UX so the scenario list can remain explicitly unselected on a fresh page session.

## Still open

- Accept R31AD on a live Windows SEND bundle: the proof target is "Animator opens, road visible on first frame, no `_circle_line_vertices` crash in logs".
- Keep Web UI idle-CPU work from R31AA/R31AB as a separate acceptance lane; this hotfix intentionally did not mix another browser pass into the same release.
- Keep cylinder/packaging visualization under regression watch: user-facing overlay bugs must stay fail-soft and must never again mask the road by crashing the first frame.
