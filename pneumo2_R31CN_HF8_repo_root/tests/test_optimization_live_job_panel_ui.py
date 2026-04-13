from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_baseline_source import (
    write_baseline_source_artifact,
)
from pneumo_solver_ui.optimization_live_job_panel_ui import (
    render_live_optimization_job_panel,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, *, buttons: dict[str, bool] | None = None, checkbox_value: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self._buttons = dict(buttons or {})
        self._checkbox_value = bool(checkbox_value)

    def info(self, text: str) -> None:
        self.calls.append(("info", text))

    def warning(self, text: str) -> None:
        self.calls.append(("warning", text))

    def error(self, text: str) -> None:
        self.calls.append(("error", text))

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def markdown(self, text: str) -> None:
        self.calls.append(("markdown", text))

    def write(self, text: str) -> None:
        self.calls.append(("write", text))

    def code(self, text: str) -> None:
        self.calls.append(("code", text))

    def progress(self, value: float) -> None:
        self.calls.append(("progress", value))

    def checkbox(self, label: str, *, value: bool, key: str, help: str) -> bool:
        self.calls.append(("checkbox", label))
        return self._checkbox_value

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", label))
        return bool(self._buttons.get(label, False))

    def columns(self, spec):
        count = int(spec) if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(count)]


def test_live_job_panel_renders_staged_runtime_and_soft_stop_state() -> None:
    st = _FakeStreamlit()
    events: list[str] = []
    job = SimpleNamespace(
        pipeline_mode="staged",
        budget=12,
        stop_file=Path("C:/tmp/STOP_OPTIMIZATION.txt"),
        proc=SimpleNamespace(pid=123),
    )

    rendered = render_live_optimization_job_panel(
        st,
        job,
        log_text="abc\nxyz",
        soft_stop_requested=True,
        coordinator_done=None,
        render_stage_runtime=lambda: events.append("stage_runtime"),
        write_soft_stop_file_fn=lambda _: True,
        terminate_process_fn=lambda _: events.append("terminate"),
        rerun_fn=lambda _: events.append("rerun"),
        sleep_fn=lambda _: events.append("sleep"),
        running_message="running",
        soft_stop_active_message="soft-stop active",
        soft_stop_label="РЎС‚РѕРї (РјСЏРіРєРѕ)",
        soft_stop_help="soft help",
        soft_stop_success_message="soft ok",
        soft_stop_error_message="soft fail",
        hard_stop_label="РЎС‚РѕРї (Р¶С‘СЃС‚РєРѕ)",
        hard_stop_help="hard help",
        hard_stop_warning_message="hard stop sent",
        hard_stop_with_stopfile_warning="stopfile failed",
        hard_only_label="РћСЃС‚Р°РЅРѕРІРёС‚СЊ (Р¶С‘СЃС‚РєРѕ)",
        hard_only_help="hard only help",
        hard_only_error_prefix="hard error",
        refresh_label="РћР±РЅРѕРІРёС‚СЊ",
        refresh_help="refresh help",
        auto_refresh_label="РђРІС‚РѕвЂ‘РѕР±РЅРѕРІР»СЏС‚СЊ СЃС‚СЂР°РЅРёС†Сѓ (РєР°Р¶РґС‹Рµ ~2 СЃРµРєСѓРЅРґС‹)",
        auto_refresh_help="auto help",
        auto_refresh_default=False,
        current_problem_hash="ph_live_scope_123456",
        current_problem_hash_mode="stable",
    )

    assert rendered is True
    assert ("info", "running") in st.calls
    assert ("warning", "soft-stop active") in st.calls
    assert ("code", "abc\nxyz") in st.calls
    assert "stage_runtime" in events


def test_live_job_panel_handles_coordinator_progress_and_hard_stop(tmp_path: Path) -> None:
    run_dir = tmp_path / "coord-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "problem_hash.txt").write_text("ph_live_scope_123456", encoding="utf-8")
    (run_dir / "problem_hash_mode.txt").write_text("legacy", encoding="utf-8")
    write_baseline_source_artifact(
        run_dir,
        {
            "source_kind": "scoped",
            "source_label": "scoped baseline",
            "baseline_path": str(
                tmp_path / "workspace" / "baselines" / "by_problem" / "p_demo" / "baseline_best.json"
            ),
        },
    )
    st = _FakeStreamlit(buttons={"РћСЃС‚Р°РЅРѕРІРёС‚СЊ (Р¶С‘СЃС‚РєРѕ)": True})
    events: list[str] = []
    job = SimpleNamespace(
        pipeline_mode="coordinator",
        budget=20,
        stop_file=None,
        proc=SimpleNamespace(pid=123),
        run_dir=run_dir,
    )

    rendered = render_live_optimization_job_panel(
        st,
        job,
        log_text="coordinator log",
        soft_stop_requested=False,
        coordinator_done=5,
        active_runtime_summary={
            "done": 5,
            "budget": 20,
            "tail_state": "trial=5 status=RUNNING",
            "trial_health": {"done": 5, "running": 2, "error": 1},
            "penalty_gate": {
                "infeasible_done": 1,
                "penalty_key": "penalty_total",
                "penalty_tol": 0.25,
                "last_penalty": 0.6,
                "objective_drift": {"comfort": 0.7, "energy": 3.5},
            },
            "recent_errors": ["bad physics", "solver diverged badly on wheel hop"],
            "handoff_provenance": {
                "source_run_name": "staged-run",
                "selection_pool": "promotable",
                "seed_count": 6,
                "unique_param_candidates": 6,
                "promotable_rows": 7,
                "staged_rows_ok": 9,
                "pipeline_hint": "staged_then_coordinator",
                "fragment_count": 4,
                "has_full_ring": True,
            },
        },
        render_stage_runtime=None,
        write_soft_stop_file_fn=lambda _: True,
        terminate_process_fn=lambda _: events.append("terminate"),
        rerun_fn=lambda _: events.append("rerun"),
        sleep_fn=lambda _: events.append("sleep"),
        running_message="running",
        soft_stop_active_message="soft-stop active",
        soft_stop_label="РЎС‚РѕРї (РјСЏРіРєРѕ)",
        soft_stop_help="soft help",
        soft_stop_success_message="soft ok",
        soft_stop_error_message="soft fail",
        hard_stop_label="РЎС‚РѕРї (Р¶С‘СЃС‚РєРѕ)",
        hard_stop_help="hard help",
        hard_stop_warning_message="hard stop sent",
        hard_stop_with_stopfile_warning="stopfile failed",
        hard_only_label="РћСЃС‚Р°РЅРѕРІРёС‚СЊ (Р¶С‘СЃС‚РєРѕ)",
        hard_only_help="hard only help",
        hard_only_error_prefix="hard error",
        refresh_label="РћР±РЅРѕРІРёС‚СЊ",
        refresh_help="refresh help",
        auto_refresh_label="РђРІС‚РѕвЂ‘РѕР±РЅРѕРІР»СЏС‚СЊ СЃС‚СЂР°РЅРёС†Сѓ (РєР°Р¶РґС‹Рµ ~2 СЃРµРєСѓРЅРґС‹)",
        auto_refresh_help="auto help",
        auto_refresh_default=False,
        current_problem_hash="ph_live_scope_123456",
        current_problem_hash_mode="legacy",
    )

    assert rendered is True
    assert ("progress", 0.25) in st.calls
    assert any(
        kind == "caption" and "5" in str(text) and "20" in str(text)
        for kind, text in st.calls
    )
    assert ("markdown", "**Runtime diagnostics**") in st.calls
    assert any(
        kind == "caption"
        and "DONE=5, RUNNING=2, ERROR=1" in str(text)
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Active run penalty gate:" in str(text)
        and "infeasible DONE=1" in str(text)
        and "`penalty_total`=0.6 > 0.25" in str(text)
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Recent run errors:" in str(text)
        and "bad physics" in str(text)
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Run provenance:" in str(text)
        and "source=staged-run" in str(text)
        for kind, text in st.calls
    )
    assert ("write", "**Baseline source:** scoped baseline") in st.calls
    assert ("write", "**Problem scope:** `ph_live_scop`") in st.calls
    assert any(kind == "caption" and "Hash mode:" in str(text) and "legacy" in str(text) for kind, text in st.calls)
    assert any(
        kind == "caption" and "Baseline override at launch:" in str(text) and "baseline_best.json" in str(text)
        for kind, text in st.calls
    )
    assert any(kind == "caption" and "matches current launch contract" in str(text) for kind, text in st.calls)
    assert any(kind == "caption" and "Hash mode matches current launch contract" in str(text) for kind, text in st.calls)
    assert ("warning", "hard stop sent") in st.calls
    assert events == ["terminate", "rerun"]
