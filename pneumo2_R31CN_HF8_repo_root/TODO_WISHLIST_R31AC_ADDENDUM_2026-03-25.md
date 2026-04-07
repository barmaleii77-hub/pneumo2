# TODO / Wishlist addendum — R31AC (2026-03-25)

## TODO
- [x] Find the real cause of the latest “Animator hangs / road is not visible” report from `logs.zip` + `runs.zip` + latest SEND bundle.
- [x] Confirm whether road/export assets are actually present in the bundle.
- [x] Fix the first-frame Desktop Animator crash in `Car3DWidget._corner_is_front`.
- [x] Add a regression test for the helper binding contract.
- [ ] Re-check on a fresh Windows SEND bundle that Animator opens and paints the first frame cleanly.

## Wishlist
- Triage should explicitly distinguish `consumer crash with valid anim_latest/road assets` from `road/export data missing`.
- State-free Car3D helpers should keep explicit static/bound semantics and lightweight source-level tests, because this class of bug blocks the whole visual consumer path.
