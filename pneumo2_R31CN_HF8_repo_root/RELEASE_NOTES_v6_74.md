# PneumoApp v6_74 — Audit & Regression Fixes (post-merge)

This release focuses on **restoring lost functionality caused by merge/integration regressions** and making navigation robust.
No new engineering features were added.

## Fixes (P0 / functional)

### 1) Restored `pneumo_solver_ui.compare_ui` full API (critical)
**Problem:** Several UI modules (validation/animation/plots) import helpers/constants from `compare_ui.py`.
In the previous build, `compare_ui.py` was overwritten by a minimal stub which removed a large part of the API.
This caused ImportErrors and/or broken pages.

**Fix:** `compare_ui.py` restored to the full implementation that contains:
- `robust_minmax`, `resample_linear`, `common_time_grid`, `compute_locked_ranges`, etc.
- constants such as `BAR_PA`, `P_ATM_DEFAULT`
- bundle loaders and unit/zero-baseline utilities

### 2) Restored missing exports in `pneumo_solver_ui.ui_components` (critical)
**Problem:** `animation_cockpit_web.py` imports live components that existed on disk in `components/`,
but were not exported from `ui_components.py` → ImportError at runtime.

**Fix:** added getters:
- `get_corner_heatmap_live_component`
- `get_minimap_live_component`
- `get_road_profile_live_component`
- `get_mech_anim_quad_component`

### 3) Navigation regression fix: prevent thin wrappers from shadowing real pages
**Problem:** duplicate filenames existed in:
- `pneumo_solver_ui/pages/` (thin wrappers calling `run_page(...)`)
- `pneumo_solver_ui/pages_legacy/` (real implementations)

The old discovery logic used "first wins", so wrappers **silently replaced** real pages → user sees dead links / “в разработке”.

**Fix:** page discovery now prefers:
1) non-wrapper implementation (if duplicate exists)
2) larger file (more likely real page)
3) tie-break: prefer `pages/` over `pages_legacy/`

This restores access to working pages like:
- `03_Design_Advisor.py`
- `04_DistributedOptimization.py`
- `05_ParamInfluence.py`
- `20_ExperimentDB.py`
- `40_DesktopAnimator.py`
- `89_ReleaseInfo.py`
- `97_UnitTests_Quick.py`
(and other duplicates that were previously shadowed)

## Diagnostics / tooling
- Expanded `tools/selfcheck.py` to verify assets for all shipped Streamlit components, including the live components above.

## Versioning
- `VERSION.txt`, `release_tag.json`, `pneumo_solver_ui/release_info.py`, `app.py` updated to **v6_74**.

