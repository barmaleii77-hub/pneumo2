from __future__ import annotations

"""Unified parameter registry helpers.

This module is intentionally small and dependency-light.

ABSOLUTE LAW (enforced by convention + validation):
  - No invented parameters.
  - No aliases / no silent compatibility bridges.
  - Any derived helpers MUST be marked SERVICE/DERIVED and ideally named with `svc__*`.

The source of truth is:
  pneumo_solver_ui/contracts/param_registry.yaml
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import logging

try:
    import yaml
except Exception as e:  # pragma: no cover
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    # .../pneumo_solver_ui/contracts/registry.py -> parents[2] == PneumoApp_v6_80
    return Path(__file__).resolve().parents[2]


def _try_event_logger():
    """Best-effort bridge to the diagnostics event logger.

    We do NOT fail if diagnostics are unavailable.
    """

    try:
        from pneumo_solver_ui.diag.eventlog import get_global_logger

        return get_global_logger(_project_root())
    except Exception:
        return None


def _emit_warning(title: str, message: str, **fields: Any) -> None:
    logger.warning("%s: %s | %s", title, message, fields)
    ev = _try_event_logger()
    if ev is not None:
        try:
            ev.warning(title, message, **fields)
        except Exception:
            # Never allow logging to break runtime.
            logger.debug("Event logger failed", exc_info=True)


def _emit_error(title: str, message: str, **fields: Any) -> None:
    logger.error("%s: %s | %s", title, message, fields)
    ev = _try_event_logger()
    if ev is not None:
        try:
            ev.error(title, message, **fields)
        except Exception:
            logger.debug("Event logger failed", exc_info=True)


@dataclass(frozen=True)
class ParamRegistry:
    """Parsed view of param_registry.yaml."""

    raw: Dict[str, Any]
    path: Path

    @property
    def canonical(self) -> Dict[str, Any]:
        return dict(self.raw.get("canonical", {}))

    @property
    def service_derived(self) -> List[Dict[str, Any]]:
        return list(self.raw.get("service_derived", []))

    @property
    def legacy_for_migration_only(self) -> Dict[str, Any]:
        return dict(self.raw.get("legacy_for_migration_only", {}))

    def is_service_key(self, key: str) -> bool:
        if key.startswith("svc__"):
            return True
        for item in self.service_derived:
            if isinstance(item, dict) and item.get("key") == key:
                return True
        return False

    def validate_required(
        self,
        available: Iterable[str],
        required: Sequence[str],
        *,
        context: str,
        strict: bool = False,
    ) -> Tuple[bool, List[str]]:
        """Check that all required keys are present.

        Returns (ok, missing).

        If strict=True, emits an error.
        Otherwise emits a warning.
        """

        a: Set[str] = set(available)
        missing = [k for k in required if k not in a]
        if missing:
            msg = f"Missing required keys: {missing}"
            if strict:
                _emit_error("CONTRACT_MISSING_KEYS", msg, context=context)
            else:
                _emit_warning("CONTRACT_MISSING_KEYS", msg, context=context)
            return False, missing
        return True, []


def load_registry(path: Optional[Path] = None) -> ParamRegistry:
    if path is None:
        path = Path(__file__).with_name("param_registry.yaml")

    if yaml is None:
        _emit_error(
            "REGISTRY_YAML_MISSING",
            "PyYAML is not available; cannot load param_registry.yaml",
            path=str(path),
        )
        return ParamRegistry(raw={}, path=path)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise TypeError(f"Expected mapping at root, got: {type(raw)}")
        return ParamRegistry(raw=raw, path=path)
    except Exception as e:
        _emit_error("REGISTRY_LOAD_FAILED", str(e), path=str(path))
        return ParamRegistry(raw={}, path=path)
