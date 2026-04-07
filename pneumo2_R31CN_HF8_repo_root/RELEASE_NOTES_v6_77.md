# UnifiedPneumoApp — Release v6_77

## Focus

P0 stability / no regression: preserve existing functionality while removing UI/navigation crashes.

## Changes vs v6_76

### P0: multipage navigation stability

- Legacy pages no longer crash the unified Streamlit app due to repeated `st.set_page_config()` calls.
  All `pages_legacy/*.py` files were migrated to use `safe_set_page_config()`.

### Compatibility helper

- Added `pneumo_solver_ui/streamlit_compat.py` with `safe_set_page_config()`.
  This allows legacy pages to be executed:
  - standalone, and
  - within the unified multipage app
  without breaking Streamlit’s "set_page_config can only be called once" rule.

### Version metadata

- Version markers synchronized for this build:
  - `VERSION.txt`
  - `release_tag.json`
  - `pneumo_solver_ui/release_info.py`

### Cleanup

- Removed stale artifact `pneumo_solver_ui/scheme_fingerprint.MISMATCH.current.json` (was misleading; not used when fingerprint matches).

## QC

- `preflight_gate`: OK (see `REPORTS/PREFLIGHT_GATE_v6_77.txt`)
- `self_check`: OK

## Notes

No feature removals. No intentional functional changes to solver physics; this release is UI/integration robustness.
