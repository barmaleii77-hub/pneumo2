from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.ui_cache_helpers import (
    atomic_write_csv,
    atomic_write_text,
    baseline_cache_base_path,
    baseline_cache_last_ptr_path,
    baseline_cache_meta_path,
    baseline_cache_table_path,
    baseline_cache_tests_path,
    detail_cache_path,
    df_to_excel_bytes,
    float_tag,
    legacy_detail_cache_path,
    load_baseline_cache,
    load_detail_cache_payload,
    load_last_baseline_ptr,
    make_detail_cache_key,
    pareto_front_2d,
    save_baseline_cache,
    save_detail_cache_payload,
    save_last_baseline_ptr,
    stable_obj_hash,
)


ROOT = Path(__file__).resolve().parents[1]


def test_pareto_front_2d_keeps_non_dominated_points() -> None:
    df = pd.DataFrame(
        {
            "a": [1.0, 2.0, 1.5, 3.0],
            "b": [3.0, 2.0, 4.0, 1.0],
        }
    )
    keep = pareto_front_2d(df, "a", "b")
    assert keep.tolist() == [True, True, False, True]


def test_cache_helpers_produce_stable_export_hash_and_key_shapes() -> None:
    xlsx = df_to_excel_bytes({"signals": pd.DataFrame({"x": [1, 2]})})
    assert xlsx[:2] == b"PK"
    assert stable_obj_hash({"b": 2, "a": 1}) == stable_obj_hash({"a": 1, "b": 2})
    assert float_tag(0.125) == "0p125"
    assert make_detail_cache_key("abc", "test_1", 0.01, 2.5, 1000, True) == "abc::test_1::dt0p01::t2p5::mp1000::full1"


def test_cache_helpers_build_expected_paths_and_write_atomically(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "baseline" / "run_1"
    workspace_dir = tmp_path / "workspace"

    assert baseline_cache_meta_path(cache_dir) == cache_dir / "meta.json"
    assert baseline_cache_table_path(cache_dir) == cache_dir / "baseline_table.csv"
    assert baseline_cache_tests_path(cache_dir) == cache_dir / "tests_map.json"
    assert baseline_cache_base_path(cache_dir) == cache_dir / "base_override.json"
    assert baseline_cache_last_ptr_path(workspace_dir) == workspace_dir / "cache" / "baseline" / "_last_baseline.json"

    text_path = cache_dir / "meta.json"
    atomic_write_text(text_path, '{"ok": true}')
    assert text_path.read_text(encoding="utf-8") == '{"ok": true}'
    assert not text_path.with_suffix(".json.tmp").exists()

    csv_path = cache_dir / "baseline_table.csv"
    atomic_write_csv(csv_path, pd.DataFrame({"x": [1, 2]}))
    assert csv_path.exists()
    assert not csv_path.with_suffix(".csv.tmp").exists()


def test_cache_helpers_build_canonical_and_legacy_detail_paths() -> None:
    cache_dir = Path("C:/tmp/cache")
    sanitize = lambda value: value.replace(" ", "_").lower()

    assert detail_cache_path(
        cache_dir,
        "Test 1",
        0.01,
        2.5,
        1000,
        True,
        sanitize_test_name=sanitize,
        float_tag_fn=float_tag,
    ) == cache_dir / "detail" / "test_1__dt0p01__t2p5__mp1000__full1.pkl.gz"
    assert legacy_detail_cache_path(
        cache_dir,
        "Test 1",
        1000,
        False,
        sanitize_test_name=sanitize,
    ) == cache_dir / "detail" / "test_1__mp1000__full0.pkl.gz"


def test_cache_helpers_roundtrip_baseline_cache_and_last_pointer(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "baseline" / "run_1"
    workspace_dir = tmp_path / "workspace"
    df = pd.DataFrame({"name": ["t1"], "score": [1.5]})

    def _json_safe(obj):
        if isinstance(obj, dict):
            return {str(key): _json_safe(value) for key, value in obj.items()}
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, tuple):
            return [_json_safe(value) for value in obj]
        return obj

    save_baseline_cache(
        cache_dir,
        df,
        {"enabled": {"t1", "t2"}},
        {"base": ("v1", "v2")},
        {"source": "pytest"},
        workspace_dir=workspace_dir,
        json_safe_fn=_json_safe,
    )

    loaded = load_baseline_cache(cache_dir)
    assert loaded is not None
    assert loaded["baseline_df"].to_dict(orient="records") == [{"name": "t1", "score": 1.5}]
    assert loaded["tests_map"] == {"enabled": ["t1", "t2"]}
    assert loaded["base_override"] == {"base": ["v1", "v2"]}
    assert loaded["meta"] == {"source": "pytest"}

    pointer = load_last_baseline_ptr(workspace_dir=workspace_dir)
    assert pointer is not None
    assert pointer["cache_dir"] == str(cache_dir)
    assert pointer["meta"] == {"source": "pytest"}


def test_cache_helpers_save_last_baseline_ptr_is_idempotent(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "baseline" / "run_2"
    workspace_dir = tmp_path / "workspace"

    save_last_baseline_ptr(cache_dir, {"rev": "HF8"}, workspace_dir=workspace_dir)
    save_last_baseline_ptr(cache_dir, {"rev": "HF8"}, workspace_dir=workspace_dir)

    pointer = load_last_baseline_ptr(workspace_dir=workspace_dir)
    assert pointer is not None
    assert pointer["cache_dir"] == str(cache_dir)
    assert pointer["meta"] == {"rev": "HF8"}


def test_cache_helpers_roundtrip_detail_cache_payload(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "detail"
    payload = {"signals": [1, 2, 3], "meta": {"source": "pytest"}}
    sanitize = lambda value: value.replace(" ", "_").lower()

    saved = save_detail_cache_payload(
        cache_dir,
        "Test 1",
        0.01,
        2.5,
        1000,
        True,
        payload,
        sanitize_test_name=sanitize,
        dump_payload_fn=lambda handle, obj: pickle.dump(obj, handle, protocol=pickle.HIGHEST_PROTOCOL),
        float_tag_fn=float_tag,
    )
    assert saved == cache_dir / "detail" / "test_1__dt0p01__t2p5__mp1000__full1.pkl.gz"

    loaded = load_detail_cache_payload(
        cache_dir,
        "Test 1",
        0.01,
        2.5,
        1000,
        True,
        sanitize_test_name=sanitize,
        load_payload_fn=lambda handle: pickle.load(handle),
        float_tag_fn=float_tag,
    )
    assert loaded == payload


def test_cache_helpers_load_detail_cache_payload_migrates_legacy_file(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "detail"
    payload = {"signals": [10, 20], "meta": {"legacy": True}}
    sanitize = lambda value: value.replace(" ", "_").lower()
    legacy_path = legacy_detail_cache_path(
        cache_dir,
        "Test 1",
        1000,
        False,
        sanitize_test_name=sanitize,
    )
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(legacy_path, "wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)

    def _resave(loaded_payload):
        return save_detail_cache_payload(
            cache_dir,
            "Test 1",
            0.02,
            5.0,
            1000,
            False,
            loaded_payload,
            sanitize_test_name=sanitize,
            dump_payload_fn=lambda handle, obj: pickle.dump(obj, handle, protocol=pickle.HIGHEST_PROTOCOL),
            float_tag_fn=float_tag,
        )

    loaded = load_detail_cache_payload(
        cache_dir,
        "Test 1",
        0.02,
        5.0,
        1000,
        False,
        sanitize_test_name=sanitize,
        load_payload_fn=lambda handle: pickle.load(handle),
        resave_payload_fn=_resave,
        float_tag_fn=float_tag,
    )
    assert loaded == payload
    assert detail_cache_path(
        cache_dir,
        "Test 1",
        0.02,
        5.0,
        1000,
        False,
        sanitize_test_name=sanitize,
        float_tag_fn=float_tag,
    ).exists()


def test_large_ui_entrypoints_import_shared_cache_helpers() -> None:
    for rel in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_cache_helpers import (" in src
        assert "detail_cache_path as build_detail_cache_path" in src
        assert "pareto_front_2d" in src
        assert "df_to_excel_bytes" in src
        assert "legacy_detail_cache_path as build_legacy_detail_cache_path" in src
        assert "load_baseline_cache as load_ui_baseline_cache" in src
        assert "load_detail_cache_payload as load_ui_detail_cache" in src
        assert "load_last_baseline_ptr as load_ui_last_baseline_ptr" in src
        assert "save_baseline_cache as save_ui_baseline_cache" in src
        assert "save_detail_cache_payload as save_ui_detail_cache" in src
        assert "save_last_baseline_ptr as save_ui_last_baseline_ptr" in src
        assert "stable_obj_hash" in src
        assert "float_tag as _float_tag" in src
        assert "make_detail_cache_key" in src
        assert "# Shared baseline-cache wrappers override the legacy inline copies above." in src
        assert "# Shared detail-cache wrappers override the legacy inline copies above." in src
        assert "return save_ui_last_baseline_ptr(cache_dir, meta, workspace_dir=WORKSPACE_DIR)" in src
        assert "return load_ui_last_baseline_ptr(workspace_dir=WORKSPACE_DIR)" in src
        assert "return load_ui_baseline_cache(cache_dir)" in src
        assert "return save_ui_detail_cache(" in src
        assert "return load_ui_detail_cache(" in src
        assert "return save_ui_baseline_cache(" in src
        assert "_legacy_save_last_baseline_ptr_dead" not in src
        assert "_legacy_load_last_baseline_ptr_dead" not in src
        assert "_legacy_load_baseline_cache_dead" not in src
        assert "_legacy_save_baseline_cache_dead" not in src
        assert "_legacy_save_detail_cache_dead" not in src
        assert "_legacy_load_detail_cache_dead" not in src
        assert src.count("def save_last_baseline_ptr(") == 1
        assert src.count("def load_last_baseline_ptr(") == 1
        assert src.count("def load_baseline_cache(") == 1
        assert src.count("def save_baseline_cache(") == 1
        assert src.count("def save_detail_cache(") == 1
        assert src.count("def load_detail_cache(") == 1
        assert "atomic_write_csv as _atomic_write_csv" not in src
        assert "atomic_write_text as _atomic_write_text" not in src
        assert "baseline_cache_base_path as _baseline_cache_base_path" not in src
        assert "baseline_cache_last_ptr_path as build_baseline_cache_last_ptr_path" not in src
        assert "baseline_cache_meta_path as _baseline_cache_meta_path" not in src
        assert "baseline_cache_table_path as _baseline_cache_table_path" not in src
        assert "baseline_cache_tests_path as _baseline_cache_tests_path" not in src
        assert "def _baseline_cache_meta_path(" not in src
        assert "def _baseline_cache_table_path(" not in src
        assert "def _baseline_cache_tests_path(" not in src
        assert "def _baseline_cache_base_path(" not in src
        assert "def _baseline_cache_last_ptr_path(" not in src
        assert "def _atomic_write_text(" not in src
        assert "def _atomic_write_csv(" not in src
        assert "def detail_cache_path(" not in src
        assert "def legacy_detail_cache_path(" not in src
        assert "def pareto_front_2d(" not in src
        assert "def df_to_excel_bytes(" not in src
        assert "def stable_obj_hash(" not in src
        assert "def _float_tag(" not in src
        assert "def make_detail_cache_key(" not in src
