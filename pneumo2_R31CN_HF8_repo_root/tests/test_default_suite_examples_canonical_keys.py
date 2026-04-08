from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.opt_worker_v3_margins_energy import build_test_suite

ROOT = Path(__file__).resolve().parents[1]
SUITE_FILES = sorted((ROOT / "pneumo_solver_ui").glob("default_suite*.json"))
FORBIDDEN_SUITE_KEYS = {
    "road_speed_mps": "vx0_м_с",
    "speed_mps": "vx0_м_с",
    "v0_м_с": "vx0_м_с",
    "скорость_м_с": "vx0_м_с",
    "road_profile_path": "road_csv",
    "road_profile_csv": "road_csv",
}
REQUIRED_PACKAGING_TARGETS = {
    "target_мин_зазор_пружина_цилиндр_м",
    "target_мин_зазор_пружина_пружина_м",
    "target_макс_ошибка_midstroke_t0_м",
    "target_мин_запас_до_coil_bind_пружины_м",
}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_suite_examples_do_not_contain_forbidden_legacy_keys() -> None:
    assert SUITE_FILES, "default suite JSON files not found"
    violations: list[str] = []
    for path in SUITE_FILES:
        payload = _load_json(path)
        assert isinstance(payload, list), f"{path.name} must contain a JSON list"
        for idx, rec in enumerate(payload):
            assert isinstance(rec, dict), f"{path.name}[{idx}] must be a JSON object"
            for legacy, canonical in FORBIDDEN_SUITE_KEYS.items():
                if legacy in rec:
                    violations.append(
                        f"{path.name}[{idx}] contains forbidden key '{legacy}' (use '{canonical}')"
                    )
    assert not violations, "\n".join(violations)


def test_default_suite_long_bump_diag_speed_comes_from_per_test_vx0() -> None:
    path = ROOT / "pneumo_solver_ui" / "default_suite_long.json"
    suite = _load_json(path)
    source_speed_by_name = {
        str(rec["имя"]): float(rec["vx0_м_с"])
        for rec in suite
        if isinstance(rec, dict)
        and str(rec.get("тип") or "") == "кочка_диагональ"
        and "vx0_м_с" in rec
    }
    assert source_speed_by_name, "default_suite_long.json must define canonical vx0_м_с for bump_diag tests"
    enabled_suite = [
        {**rec, "включен": True} if isinstance(rec, dict) and str(rec.get("тип") or "") == "кочка_диагональ" else rec
        for rec in suite
    ]

    cfg = {
        "suite": enabled_suite,
        "скорость_м_с_по_умолчанию": 77.0,
        "колея": 1.2,
        "база": 2.3,
    }
    built = build_test_suite(cfg)
    built_speed_by_name = {
        str(name): float(test["v"])
        for name, test, *_ in built
        if isinstance(test, dict) and str(name).startswith("кочка_диагональ")
    }

    assert source_speed_by_name.keys() <= built_speed_by_name.keys()
    for name, expected_speed in source_speed_by_name.items():
        assert built_speed_by_name[name] == expected_speed, (
            f"{name}: build_test_suite must use per-test vx0_м_с={expected_speed} from default_suite_long.json, "
            f"got {built_speed_by_name[name]}"
        )


def test_default_suite_examples_include_family_packaging_targets_for_penalty_rows() -> None:
    violations: list[str] = []
    for path in SUITE_FILES:
        payload = _load_json(path)
        for idx, rec in enumerate(payload):
            if not isinstance(rec, dict):
                continue
            has_targets = any(str(k).startswith("target_") for k in rec.keys())
            is_ring = str(rec.get("имя") or "").strip() == "ring_город_неровная_дорога_20кмч_15s"
            if not (has_targets or is_ring):
                continue
            missing = sorted(key for key in REQUIRED_PACKAGING_TARGETS if key not in rec)
            if missing:
                violations.append(f"{path.name}[{idx}] missing packaging targets: {', '.join(missing)}")
    assert not violations, "\n".join(violations)
