from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.opt_stage_runner_v1 import (
    append_csv_to_archive_jsonl,
    collect_seed_points,
    make_initial_cem_state_from_archive,
)
from pneumo_solver_ui.optimization_defaults import (
    DEFAULT_OPTIMIZATION_OBJECTIVES,
    DIST_OPT_PENALTY_KEY_DEFAULT,
)
from pneumo_solver_ui.optimization_objective_contract import (
    LEGACY_STAGE_RUNNER_OBJECTIVES,
    objective_contract_payload,
)


OBJECTIVE_KEYS = tuple(str(x) for x in DEFAULT_OPTIMIZATION_OBJECTIVES)
PENALTY_KEY = str(DIST_OPT_PENALTY_KEY_DEFAULT)


def _archive_row(
    *,
    rid: int,
    foo: float,
    score: tuple[float, float, float, float],
    contract: dict | None = None,
    problem_hash: str = "",
) -> dict:
    row = {
        "id": int(rid),
        "candidate_role": "search",
        "meta_source": "search",
        "ошибка": "",
        "pruned_early": 0.0,
        "pruned_after_test": "",
        PENALTY_KEY: float(score[0]),
        f"параметр__foo": float(foo),
    }
    for key, value in zip(OBJECTIVE_KEYS, score[1:4]):
        row[str(key)] = float(value)
    if contract is not None:
        row["objective_contract"] = dict(contract)
    if problem_hash:
        row["problem_hash"] = str(problem_hash)
    return row


def test_stage_archive_rows_persist_problem_hash_and_objective_contract(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    pd.DataFrame([
        _archive_row(rid=101, foo=2.0, score=(0.0, 1.0, 2.0, 3.0)),
    ]).to_csv(csv_path, index=False)

    archive_path = tmp_path / "global_history.jsonl"
    append_csv_to_archive_jsonl(
        archive_path,
        csv_path,
        meta={
            "ts": "2026-04-10 12:00:00",
            "run_dir": str(tmp_path / "run"),
            "problem_hash": "ph_stage_contract",
            "objective_contract": objective_contract_payload(
                objective_keys=OBJECTIVE_KEYS,
                penalty_key=PENALTY_KEY,
                source="stage_archive_test",
            ),
        },
        stage_name="stage0_relevance",
        archived_ids_path=tmp_path / "_archived_ids.json",
    )

    rows = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["problem_hash"] == "ph_stage_contract"
    assert rows[0]["objective_contract"]["penalty_key"] == PENALTY_KEY
    assert rows[0]["objective_contract"]["objective_keys"] == list(OBJECTIVE_KEYS)


def test_collect_seed_points_prefers_same_problem_archive_and_skips_contract_mismatch(tmp_path: Path) -> None:
    archive_path = tmp_path / "global_history.jsonl"
    same_contract = objective_contract_payload(
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        source="seed_test_same_contract",
    )
    mismatched_contract = objective_contract_payload(
        objective_keys=LEGACY_STAGE_RUNNER_OBJECTIVES,
        penalty_key=PENALTY_KEY,
        source="seed_test_mismatch",
    )
    rows = [
        _archive_row(
            rid=301,
            foo=9.0,
            score=(0.0, 0.01, 0.01, 0.01),
            contract=mismatched_contract,
            problem_hash="ph_stage_contract",
        ),
        _archive_row(
            rid=302,
            foo=8.0,
            score=(0.0, 0.05, 0.05, 0.05),
            contract=same_contract,
            problem_hash="ph_other_contract_compatible",
        ),
        _archive_row(
            rid=303,
            foo=2.0,
            score=(0.0, 0.20, 0.20, 0.20),
            contract=same_contract,
            problem_hash="ph_stage_contract",
        ),
    ]
    with archive_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    seeds = collect_seed_points(
        stage_idx=1,
        stage_csvs=[("stage0_relevance", tmp_path / "missing_stage0.csv"), ("stage1_long", tmp_path / "stage1.csv")],
        archive_path=archive_path,
        ranges={"foo": [0.0, 10.0]},
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        problem_hash="ph_stage_contract",
        max_prev=0,
        max_archive=8,
        max_total=8,
    )

    assert len(seeds) == 1
    assert float(seeds[0]["foo"]) == 2.0


def test_archive_warmstart_uses_preferred_compatible_bucket(tmp_path: Path) -> None:
    archive_path = tmp_path / "global_history.jsonl"
    same_contract = objective_contract_payload(
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        source="warmstart_same_contract",
    )
    mismatched_contract = objective_contract_payload(
        objective_keys=LEGACY_STAGE_RUNNER_OBJECTIVES,
        penalty_key=PENALTY_KEY,
        source="warmstart_mismatch",
    )
    rows = [
        _archive_row(
            rid=401,
            foo=9.0,
            score=(0.0, 0.01, 0.01, 0.01),
            contract=mismatched_contract,
            problem_hash="ph_stage_contract",
        ),
        _archive_row(
            rid=402,
            foo=8.0,
            score=(0.0, 0.05, 0.05, 0.05),
            contract=same_contract,
            problem_hash="ph_other_contract_compatible",
        ),
        _archive_row(
            rid=403,
            foo=2.0,
            score=(0.0, 0.20, 0.20, 0.20),
            contract=same_contract,
            problem_hash="ph_stage_contract",
        ),
        _archive_row(
            rid=404,
            foo=2.5,
            score=(0.0, 0.25, 0.25, 0.25),
            contract=same_contract,
            problem_hash="ph_stage_contract",
        ),
    ]
    with archive_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    cem_state_path = tmp_path / "stage_01.csv_cem_state.json"
    ok = make_initial_cem_state_from_archive(
        cem_state_path,
        archive_path,
        ranges={"foo": [0.0, 10.0]},
        objective_keys=OBJECTIVE_KEYS,
        penalty_key=PENALTY_KEY,
        problem_hash="ph_stage_contract",
        top_k=8,
    )

    assert ok is True
    state = json.loads(cem_state_path.read_text(encoding="utf-8"))
    assert state["archive_match_kind"] == "same_problem"
    assert float(state["mu"][0]) < 0.30
