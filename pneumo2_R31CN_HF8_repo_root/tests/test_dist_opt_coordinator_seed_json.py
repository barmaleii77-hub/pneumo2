from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.tools.dist_opt_coordinator import _load_seed_vectors


class _FakeCore:
    def dim(self) -> int:
        return 3

    def params_to_u(self, params: dict) -> list[float]:
        return [
            float(params.get("a", 0.0)) / 10.0,
            float(params.get("b", 0.0)) / 10.0,
            float(params.get("c", 0.0)) / 10.0,
        ]


def test_load_seed_vectors_accepts_params_and_xu_and_deduplicates(tmp_path: Path) -> None:
    seed_json = tmp_path / "seed.json"
    seed_json.write_text(
        json.dumps(
            [
                {"params": {"a": 1.0, "b": 2.0, "c": 3.0}},
                {"x_u": [0.1, 0.2, 0.3]},
                {"a": 1.0, "b": 2.0, "c": 3.0},
                [0.1, 0.2, 0.3],
                {"x_u": [0.1, 0.2]},
                {"params": {"a": "oops"}},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    loaded, meta = _load_seed_vectors(_FakeCore(), seed_json)

    assert loaded == [[0.1, 0.2, 0.3]]
    assert meta["loaded"] == 1
    assert meta["duplicates"] == 3
    assert meta["invalid"] == 2
    assert Path(meta["seed_json"]).resolve() == seed_json.resolve()
