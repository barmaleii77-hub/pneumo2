from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _reload_module():
    import pneumo_solver_ui.tools.autoselfcheck as autoselfcheck

    return importlib.reload(autoselfcheck)


def test_autoselfcheck_reuses_disk_cache_across_module_reload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("PNEUMO_AUTOCHECK_DISABLE", raising=False)

    autoselfcheck = _reload_module()
    first_calls = {"count": 0}

    def _fake_build(*, strict: bool):
        first_calls["count"] += 1
        return autoselfcheck.AutoSelfcheckResult(
            ok=True,
            elapsed_s=1.23,
            results={"compileall": {"ok": True, "rc": {"ok": True}}},
            failures=[],
            summary="autoselfcheck: PASS (1.23s)",
            messages=[],
            details={"compileall": {"ok": True, "rc": {"ok": True}}},
        )

    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_cache_fingerprint", lambda root=None: "fp-cache-hit")
    monkeypatch.setattr(autoselfcheck, "_build_autoselfcheck_result", _fake_build)

    first = autoselfcheck.ensure_autoselfcheck_once()
    cache_path = autoselfcheck._autoselfcheck_cache_path()
    assert first_calls["count"] == 1
    assert cache_path.exists()
    assert first.summary == "autoselfcheck: PASS (1.23s)"

    autoselfcheck = _reload_module()
    second_calls = {"count": 0}

    def _should_not_run(*, strict: bool):
        second_calls["count"] += 1
        raise AssertionError("disk cache was not reused")

    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_cache_fingerprint", lambda root=None: "fp-cache-hit")
    monkeypatch.setattr(autoselfcheck, "_build_autoselfcheck_result", _should_not_run)

    second = autoselfcheck.ensure_autoselfcheck_once()
    assert second_calls["count"] == 0
    assert second.ok is True
    assert second.summary == "autoselfcheck: PASS (1.23s)"


def test_autoselfcheck_invalidates_disk_cache_when_fingerprint_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(tmp_path / "workspace"))

    autoselfcheck = _reload_module()
    first_calls = {"count": 0}

    def _first_result(*, strict: bool):
        first_calls["count"] += 1
        return autoselfcheck.AutoSelfcheckResult(
            ok=True,
            elapsed_s=0.4,
            results={"import_smoke": {"ok": True, "rc": {"ok": True}}},
            failures=[],
            summary="autoselfcheck: PASS (0.40s)",
            messages=[],
            details={"import_smoke": {"ok": True, "rc": {"ok": True}}},
        )

    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_cache_fingerprint", lambda root=None: "fp-old")
    monkeypatch.setattr(autoselfcheck, "_build_autoselfcheck_result", _first_result)
    autoselfcheck.ensure_autoselfcheck_once()
    assert first_calls["count"] == 1

    autoselfcheck = _reload_module()
    second_calls = {"count": 0}

    def _second_result(*, strict: bool):
        second_calls["count"] += 1
        return autoselfcheck.AutoSelfcheckResult(
            ok=True,
            elapsed_s=0.7,
            results={"import_smoke": {"ok": True, "rc": {"ok": True}}},
            failures=[],
            summary="autoselfcheck: PASS (0.70s)",
            messages=[],
            details={"import_smoke": {"ok": True, "rc": {"ok": True}}},
        )

    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_cache_fingerprint", lambda root=None: "fp-new")
    monkeypatch.setattr(autoselfcheck, "_build_autoselfcheck_result", _second_result)

    second = autoselfcheck.ensure_autoselfcheck_once()
    assert second_calls["count"] == 1
    assert second.summary == "autoselfcheck: PASS (0.70s)"


def test_autoselfcheck_cached_failure_still_raises_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(tmp_path / "workspace"))

    autoselfcheck = _reload_module()

    def _failing_result(*, strict: bool):
        return autoselfcheck.AutoSelfcheckResult(
            ok=False,
            elapsed_s=0.2,
            results={"import_smoke": {"ok": False, "rc": {"missing": ["x"]}}},
            failures=[{"step": "import_smoke", "rc": {"missing": ["x"]}}],
            summary="autoselfcheck: FAIL (1) [import_smoke] (0.20s)",
            messages=["import_smoke: FAIL (rc={'missing': ['x']})"],
            details={"import_smoke": {"ok": False, "rc": {"missing": ["x"]}}},
        )

    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_cache_fingerprint", lambda root=None: "fp-strict")
    monkeypatch.setattr(autoselfcheck, "_build_autoselfcheck_result", _failing_result)
    first = autoselfcheck.ensure_autoselfcheck_once()
    assert first.ok is False

    autoselfcheck = _reload_module()

    def _should_not_run(*, strict: bool):
        raise AssertionError("cached strict failure should not recompute")

    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_cache_fingerprint", lambda root=None: "fp-strict")
    monkeypatch.setattr(autoselfcheck, "_build_autoselfcheck_result", _should_not_run)

    with pytest.raises(RuntimeError, match="AutoSelfcheck FAIL"):
        autoselfcheck.ensure_autoselfcheck_once(strict=True)
