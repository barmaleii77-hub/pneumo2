from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Callable

from pneumo_solver_ui.ui_diagnostics_helpers import make_ui_diagnostics_zip_bundle


def build_ui_diagnostics_zip_writer(
    *,
    here: Path,
    workspace_dir: Path,
    log_dir: Path | None,
    app_release: str,
    json_safe_fn: Callable[[Any], Any] | None = None,
):
    return partial(
        make_ui_diagnostics_zip_bundle,
        here=here,
        workspace_dir=workspace_dir,
        log_dir=log_dir,
        app_release=app_release,
        json_safe_fn=json_safe_fn,
    )
