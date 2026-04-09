from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Callable

from pneumo_solver_ui.ui_process_helpers import start_background_worker


def build_background_worker_starter(
    *,
    console_python_executable_fn: Callable[[str | Path | None], str] | None,
):
    return partial(
        start_background_worker,
        console_python_executable_fn=console_python_executable_fn,
    )
