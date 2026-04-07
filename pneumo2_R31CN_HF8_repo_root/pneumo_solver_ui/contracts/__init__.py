"""pneumo_solver_ui.contracts

ABSOLUTE LAW (read first):
  - No invented parameters.
  - No aliases / no silent compatibility bridges.
  - All keys must be aligned with the unified registry:
      pneumo_solver_ui/contracts/param_registry.yaml
  - Any locally computed helpers must be marked as SERVICE/DERIVED and preferably use
    a `svc__*` prefix.

This package provides lightweight runtime helpers around the registry.
"""

from .registry import ParamRegistry, load_registry

__all__ = ["ParamRegistry", "load_registry"]
