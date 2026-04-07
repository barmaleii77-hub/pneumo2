"""Compatibility shim for legacy imports.

Some internal tools/pages historically used ``from compare_ui import ...`` when
executed with ``pneumo_solver_ui`` as the working directory.

In the unified layout the canonical module is ``pneumo_solver_ui.compare_ui``.

This shim keeps both import styles working.
"""

from pneumo_solver_ui.compare_ui import *  # noqa: F401,F403
