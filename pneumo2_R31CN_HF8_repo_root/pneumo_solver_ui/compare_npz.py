"""NPZ bundle helpers.

This module exists to provide a small, stable API for pages/components that need
common NPZ loading logic.

Historically, NPZ loading lived in several places (Qt Compare Viewer, Streamlit
Compare pages, etc.). In the unified app, the canonical implementation is
`pneumo_solver_ui.compare_ui.load_npz_bundle`.

We keep `load_npz_dict()` as a compatibility wrapper so that older/experimental
pages (e.g. Validation Cockpit Web) can import it without duplicating logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Union

from .compare_ui import load_npz_bundle


def load_npz_dict(path: Union[str, Path]) -> Dict[str, Any]:
    """Load an NPZ bundle and return a dict with keys: `tables`, `meta`.

    Parameters
    ----------
    path:
        Path to a .npz bundle produced by the solver/tests.

    Returns
    -------
    dict
        A mapping with:
          - tables: dict[str, pandas.DataFrame]
          - meta: dict[str, Any]
    """

    return load_npz_bundle(str(path))


__all__ = ["load_npz_dict"]
