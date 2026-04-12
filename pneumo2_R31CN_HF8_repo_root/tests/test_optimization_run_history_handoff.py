from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.optimization_run_history import (
    format_run_choice,
    summarize_optimization_run,
)


def test_run_history_reads_staged_handoff_plan_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "p_staged_handoff"
    handoff_dir = run_dir / "coordinator_handoff"
    handoff_dir.mkdir(parents=True)
    (run_dir / "sp.json").write_text(
        '{"status": "done", "ts": "2026-04-12 20:00:00", "combined_csv": ""}',
        encoding="utf-8",
    )
    (run_dir / "results_all.csv").write_text("id,val\n1,2\n2,3\n", encoding="utf-8")
    (handoff_dir / "coordinator_handoff_plan.json").write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_proposer": "portfolio",
                "recommended_q": 2,
                "recommended_budget": 84,
                "seed_count": 6,
                "suite_analysis": {"family": "auto_ring"},
                "requires_full_ring_validation": True,
                "recommendation_reason": {
                    "fragment_count": 4,
                    "has_full_ring": True,
                    "pipeline_hint": "staged_then_coordinator",
                    "proposer_source": "auto_tuner",
                    "q_source": "auto_tuner",
                    "seed_bridge": {
                        "staged_rows_ok": 9,
                        "promotable_rows": 7,
                        "unique_param_candidates": 6,
                        "selection_pool": "promotable",
                        "seed_count": 6,
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
                    str(handoff_dir / "run"),
                    "--proposer",
                    "portfolio",
                    "--q",
                    "2",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = summarize_optimization_run(run_dir)

    assert summary is not None
    assert summary.handoff_available is True
    assert summary.handoff_target_run_dir == (handoff_dir / "run").resolve()
    assert summary.handoff_preset_tag == "ray/portfolio/q2"
    assert summary.handoff_budget == 84
    assert summary.handoff_seed_count == 6
    assert summary.handoff_suite_family == "auto_ring"
    assert summary.handoff_requires_full_ring_validation is True
    assert summary.handoff_fragment_count == 4
    assert summary.handoff_has_full_ring is True
    assert summary.handoff_staged_rows_ok == 9
    assert summary.handoff_promotable_rows == 7
    assert summary.handoff_unique_param_candidates == 6
    assert summary.handoff_selection_pool == "promotable"
    assert summary.handoff_pipeline_hint == "staged_then_coordinator"
    assert any("seed-bridge взял 6 кандидатов" in line for line in summary.handoff_reason_lines)
    assert "handoff=ray/portfolio/q2" in format_run_choice(summary)
