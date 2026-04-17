from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools import autoselfcheck


def test_autoselfcheck_uses_disk_cache_when_fingerprint_matches(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "pneumo_solver_ui"
    (root / "logs").mkdir(parents=True)
    monkeypatch.setattr(autoselfcheck, "_LAST", None)
    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_root", lambda: root)
    monkeypatch.setattr(autoselfcheck, "_cache_fingerprint", lambda _root: {"digest": "same", "schema": 1})

    calls = {"count": 0}

    def _fake_run(_root: Path) -> autoselfcheck.AutoSelfcheckResult:
        calls["count"] += 1
        return autoselfcheck.AutoSelfcheckResult(
            ok=True,
            elapsed_s=1.23,
            results={"step": {"ok": True}},
            failures=[],
            summary="autoselfcheck: PASS (1.23s)",
            messages=[],
            details={"step": {"ok": True}},
        )

    monkeypatch.setattr(autoselfcheck, "_run_autoselfcheck", _fake_run)

    first = autoselfcheck.ensure_autoselfcheck_once()
    assert first.ok is True
    assert calls["count"] == 1

    monkeypatch.setattr(autoselfcheck, "_LAST", None)
    second = autoselfcheck.ensure_autoselfcheck_once()
    assert second.ok is True
    assert calls["count"] == 1
    assert second.summary.endswith("[cached]")
    assert second.details["cache"]["hit"] is True


def test_autoselfcheck_recomputes_when_fingerprint_changes(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "pneumo_solver_ui"
    (root / "logs").mkdir(parents=True)
    monkeypatch.setattr(autoselfcheck, "_LAST", None)
    monkeypatch.setattr(autoselfcheck, "_autoselfcheck_root", lambda: root)

    state = {"digest": "one", "count": 0}
    monkeypatch.setattr(autoselfcheck, "_cache_fingerprint", lambda _root: {"digest": state["digest"], "schema": 1})

    def _fake_run(_root: Path) -> autoselfcheck.AutoSelfcheckResult:
        state["count"] += 1
        return autoselfcheck.AutoSelfcheckResult(
            ok=(state["count"] % 2 == 1),
            elapsed_s=float(state["count"]),
            results={"step": {"ok": state["count"] % 2 == 1}},
            failures=[],
            summary=f"run-{state['count']}",
            messages=[],
            details={"step": {"ok": state["count"] % 2 == 1}},
        )

    monkeypatch.setattr(autoselfcheck, "_run_autoselfcheck", _fake_run)

    first = autoselfcheck.ensure_autoselfcheck_once()
    assert first.summary == "run-1"
    assert state["count"] == 1

    monkeypatch.setattr(autoselfcheck, "_LAST", None)
    state["digest"] = "two"
    second = autoselfcheck.ensure_autoselfcheck_once()
    assert second.summary == "run-2"
    assert second.ok is False
    assert state["count"] == 2
