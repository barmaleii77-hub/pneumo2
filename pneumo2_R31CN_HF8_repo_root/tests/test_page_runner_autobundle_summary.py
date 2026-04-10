from __future__ import annotations

import json
import sys
import types
from pathlib import Path

# _page_runner imports streamlit at module import time; provide a tiny stub.
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.SimpleNamespace()

from pneumo_solver_ui.pages import _page_runner


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: dict[str, list[str]] = {
            "error": [],
            "caption": [],
            "success": [],
            "warning": [],
            "markdown": [],
            "title": [],
        }

    def title(self, text: str) -> None:
        self.calls["title"].append(str(text))

    def error(self, text: str) -> None:
        self.calls["error"].append(str(text))

    def caption(self, text: str) -> None:
        self.calls["caption"].append(str(text))

    def success(self, text: str) -> None:
        self.calls["success"].append(str(text))

    def warning(self, text: str) -> None:
        self.calls["warning"].append(str(text))

    def markdown(self, text: str) -> None:
        self.calls["markdown"].append(str(text))

    def expander(self, _label: str):
        return _FakeExpander()

    def exception(self, _exc: Exception) -> None:
        return None


def test_run_script_page_autobundle_surfaces_anim_and_browser_perf_summary(tmp_path: Path, monkeypatch) -> None:
    page = tmp_path / "broken_page.py"
    page.write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / "latest_send_bundle.zip"
    bundle.write_bytes(b"zip")

    (out_dir / "latest_anim_pointer_diagnostics.json").write_text(
        json.dumps(
            {
                "anim_latest_available": True,
                "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
                "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
                "anim_latest_visual_cache_token": "tok-runner",
                "anim_latest_visual_reload_inputs": ["npz", "road_csv"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "anim_latest": {
                    "available": True,
                    "visual_cache_token": "tok-runner",
                    "browser_perf_evidence_status": "trace_bundle_ready",
                    "browser_perf_evidence_level": "PASS",
                    "browser_perf_bundle_ready": True,
                    "browser_perf_comparison_status": "regression_checked",
                    "browser_perf_comparison_level": "PASS",
                    "browser_perf_comparison_ready": True,
                    "browser_perf_evidence_report_in_bundle": True,
                    "browser_perf_comparison_report_in_bundle": True,
                    "browser_perf_trace_in_bundle": True,
                },
                "optimizer_scope": {
                    "problem_hash": "ph_runner_full_1234567890",
                    "problem_hash_short": "ph_runner_1",
                    "problem_hash_mode": "stable",
                    "canonical_source": "triage",
                    "scope_sync_ok": False,
                    "mismatch_fields": ["problem_hash"],
                },
                "optimizer_scope_gate": {
                    "release_gate": "FAIL",
                    "release_gate_reason": "problem_hash mismatch between sources",
                    "release_risk": True,
                    "canonical_source": "triage",
                    "scope_sync_ok": False,
                    "mismatch_fields": ["problem_hash"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fake_st = _FakeStreamlit()
    monkeypatch.setattr(_page_runner, "st", fake_st)

    fake_bootstrap = types.SimpleNamespace(bootstrap=lambda _st: None)
    fake_crash_guard = types.SimpleNamespace(try_autosave_bundle=lambda **_: str(bundle))
    monkeypatch.setitem(sys.modules, "pneumo_solver_ui.ui_bootstrap", fake_bootstrap)
    monkeypatch.setitem(sys.modules, "pneumo_solver_ui.crash_guard", fake_crash_guard)
    monkeypatch.setattr(_page_runner.runpy, "run_path", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(_page_runner, "_copy_bundle_to_clipboard", lambda path: (True, f"copied {path}"))

    _page_runner.run_script_page(str(page), auto_bundle=True, title="Broken")

    assert any("Диагностика сохранена:" in text for text in fake_st.calls["caption"])
    assert any("Anim pointer diagnostics:" in text for text in fake_st.calls["caption"])
    assert any("Optimizer scope gate: FAIL / release_risk=True / reason=problem_hash mismatch between sources" in text for text in fake_st.calls["markdown"])
    assert any("Optimizer scope: scope=ph_runner_1 / mode=stable / source=triage / sync=False / mismatches=problem_hash" in text for text in fake_st.calls["markdown"])
    assert any("Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True" in text for text in fake_st.calls["markdown"])
    assert any("Browser perf comparison: regression_checked / PASS / ready=True" in text for text in fake_st.calls["markdown"])
    assert any("ZIP диагностики уже скопирован в буфер обмена." in text for text in fake_st.calls["success"])
