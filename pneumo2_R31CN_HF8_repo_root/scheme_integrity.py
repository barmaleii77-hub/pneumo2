"""Compatibility shim for legacy imports.

Historically, some scripts/models imported :mod:`scheme_integrity` as a *top-level*
module (e.g. ``from scheme_integrity import verify_scheme_integrity``) when they
were executed with ``pneumo_solver_ui`` as the working directory.

In the unified layout, the implementation lives in
``pneumo_solver_ui.scheme_integrity``.

This shim keeps both import styles working in a single release bundle.
"""

from pneumo_solver_ui.scheme_integrity import *  # noqa: F401,F403

