from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.optimization_coordinator_handoff_ui import (
    handoff_preset_tag,
    handoff_recommendation_reason_lines,
    render_coordinator_handoff_action,
    recommended_handoff_button_help,
    recommended_handoff_button_label,
    summarize_coordinator_handoff,
)


class _FakeStreamlit:
    def __init__(self, *, click: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self._click = bool(click)

    def caption(self, text: str) -> None:
        self.calls.append(("caption", text))

    def button(self, label: str, **kwargs) -> bool:
        self.calls.append(("button", {"label": label, **dict(kwargs)}))
        return self._click


def test_handoff_ui_summarizes_existing_plan_and_triggers_callback(tmp_path: Path) -> None:
    source_run = tmp_path / "staged_run"
    handoff_dir = source_run / "coordinator_handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "coordinator_handoff_plan.json").write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_proposer": "portfolio",
                "recommended_q": 2,
                "recommended_budget": 72,
                "requires_full_ring_validation": True,
                "seed_count": 5,
                "suite_analysis": {"family": "auto_ring"},
                "recommendation_reason": {
                    "fragment_count": 4,
                    "has_full_ring": True,
                    "pipeline_hint": "staged_then_coordinator",
                    "proposer_source": "auto_tuner",
                    "q_source": "auto_tuner",
                    "seed_bridge": {
                        "staged_rows_total": 12,
                        "staged_rows_ok": 9,
                        "promotable_rows": 7,
                        "selection_pool": "promotable",
                        "unique_param_candidates": 6,
                        "seed_count": 5,
                    },
                    "budget_formula": {
                        "base": 40,
                        "per_fragment": 4,
                        "per_seed": 2,
                        "full_ring_bonus": 24,
                    },
                },
                "cmd_args": [
                    "--backend",
                    "ray",
                    "--run-dir",
                    str(tmp_path / "coord_run"),
                    "--proposer",
                    "portfolio",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_coordinator_handoff(source_run)
    assert summary["available"] is True
    assert summary["backend"] == "ray"
    assert summary["proposer"] == "portfolio"
    assert summary["q"] == 2
    assert summary["seed_count"] == 5
    assert summary["target_run_dir"] == (tmp_path / "coord_run").resolve()
    assert summary["requires_full_ring_validation"] is True
    assert handoff_preset_tag(summary) == "ray/portfolio/q2"
    assert recommended_handoff_button_label(summary) == "Запустить рекомендованный full-ring coordinator (ray/portfolio/q2)"
    assert "budget=72" in recommended_handoff_button_help(summary)
    reason_lines = handoff_recommendation_reason_lines(summary)
    assert len(reason_lines) == 2
    assert "seed-bridge взял 5 кандидатов" in reason_lines[0]
    assert "budget=72" in reason_lines[1]
    assert "proposer=portfolio (auto_tuner)" in reason_lines[1]

    st = _FakeStreamlit(click=True)
    events: list[Path] = []
    clicked = render_coordinator_handoff_action(
        st,
        source_run_dir=source_run,
        start_handoff_fn=lambda run_dir: events.append(run_dir) or True,
        button_key="k1",
    )

    assert clicked is True
    assert any(
        kind == "caption" and "Рекомендуемое следующее действие" in text and "ray/portfolio/q2" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption"
        and "Рекомендуемый full-ring preset" in text
        and "suite=auto_ring" in text
        and "backend=ray" in text
        and "proposer=portfolio" in text
        and "q=2" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption" and "seed-bridge взял 5 кандидатов" in text and "full-ring=yes" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption" and "proposer=portfolio (auto_tuner)" in text and "budget=72" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "caption" and "длинные пользовательские кольца" in text
        for kind, text in st.calls
    )
    assert any(
        kind == "button"
        and isinstance(payload, dict)
        and payload.get("label") == "Запустить рекомендованный full-ring coordinator (ray/portfolio/q2)"
        and payload.get("type") == "primary"
        and "budget=72" in str(payload.get("help"))
        for kind, payload in st.calls
    )
    assert events == [source_run.resolve()]


def test_handoff_ui_reports_missing_plan_honestly(tmp_path: Path) -> None:
    st = _FakeStreamlit()
    clicked = render_coordinator_handoff_action(
        st,
        source_run_dir=tmp_path / "missing_run",
        start_handoff_fn=None,
        button_label="Run handoff",
        button_help="help",
        button_key="k2",
        missing_caption="handoff missing",
    )

    assert clicked is False
    assert ("caption", "handoff missing") in st.calls
