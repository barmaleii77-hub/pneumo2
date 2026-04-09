from __future__ import annotations

import builtins
import io
from pathlib import Path

from pneumo_solver_ui.ui_process_helpers import (
    dump_cloudpickle_payload,
    dump_pickle_payload,
    load_cloudpickle_payload,
    load_pickle_payload,
)


ROOT = Path(__file__).resolve().parents[1]


def test_pickle_payload_helpers_roundtrip_simple_payload() -> None:
    payload = {"signals": [1, 2, 3], "meta": {"source": "pytest"}}
    handle = io.BytesIO()

    dump_pickle_payload(handle, payload)
    handle.seek(0)

    assert load_pickle_payload(handle) == payload


def test_cloudpickle_payload_helpers_fallback_to_pickle_when_cloudpickle_missing(monkeypatch) -> None:
    payload = {"signals": [10, 20], "meta": {"fallback": True}}
    handle = io.BytesIO()
    orig_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cloudpickle":
            raise ModuleNotFoundError("No module named 'cloudpickle'")
        return orig_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    dump_cloudpickle_payload(handle, payload)
    handle.seek(0)

    assert load_cloudpickle_payload(handle) == payload


def test_large_ui_entrypoints_import_shared_process_helpers() -> None:
    for rel in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_process_helpers import (" in src
        assert "start_background_worker" in src
        assert "from pneumo_solver_ui.ui_process_profile_helpers import (" in src
        assert "start_worker = build_background_worker_starter(" in src
        assert "def _dump_detail_cache_payload(" not in src
        assert "def _load_detail_cache_payload(" not in src
        assert "def start_worker(" not in src
