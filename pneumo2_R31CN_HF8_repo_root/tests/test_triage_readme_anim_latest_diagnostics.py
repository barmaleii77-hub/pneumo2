from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.tools.make_send_bundle import _build_send_bundle_readme
from pneumo_solver_ui.tools.triage_report import generate_triage_report


ROOT = Path(__file__).resolve().parents[1]


def _make_anim_diag(token: str = "tok-123", reload_inputs: list[str] | None = None) -> dict:
    reload_inputs = list(reload_inputs or ["npz", "road_csv"])
    return {
        "anim_latest_available": True,
        "anim_latest_global_pointer_json": "/abs/workspace/_pointers/anim_latest.json",
        "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
        "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
        "anim_latest_visual_cache_token": token,
        "anim_latest_visual_reload_inputs": reload_inputs,
        "anim_latest_visual_cache_dependencies": {
            "version": 1,
            "context": "anim_latest export pointer",
            "npz": {"path": "/abs/workspace/exports/anim_latest.npz", "exists": True, "size": 123},
            "road_csv_ref": "anim_latest_road_csv.csv",
            "road_csv_path": "/abs/workspace/exports/anim_latest_road_csv.csv",
            "road_csv": {"path": "/abs/workspace/exports/anim_latest_road_csv.csv", "exists": True, "size": 77},
        },
        "anim_latest_updated_utc": "2026-03-11T12:00:00+00:00",
        "anim_latest_meta": {"road_csv": "anim_latest_road_csv.csv"},
    }



def test_generate_triage_report_exposes_anim_latest_diagnostics_from_sidecar(tmp_path: Path) -> None:
    sb_root = tmp_path / "send_bundles"
    sb_root.mkdir(parents=True, exist_ok=True)
    diag = _make_anim_diag(token="tok-triage")
    (sb_root / "latest_anim_pointer_diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (sb_root / "latest_anim_pointer_diagnostics.md").write_text(
        "# Anim latest diagnostics\n\n- token: tok-triage\n",
        encoding="utf-8",
    )

    md, summary = generate_triage_report(tmp_path, keep_last_n=1)
    anim = dict(summary.get("anim_latest") or {})
    paths = dict(summary.get("paths") or {})

    assert anim["source"] == "send_bundle_sidecar"
    assert anim["anim_latest_available"] is True
    assert anim["anim_latest_visual_cache_token"] == "tok-triage"
    assert anim["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert paths["latest_anim_pointer_diagnostics_json"] == str((sb_root / "latest_anim_pointer_diagnostics.json").resolve())
    assert paths["latest_anim_pointer_diagnostics_md"] == str((sb_root / "latest_anim_pointer_diagnostics.md").resolve())
    assert "## Anim latest diagnostics" in md
    assert "tok-triage" in md
    assert "npz, road_csv" in md
    assert "Latest anim diagnostics json" in md



def test_build_send_bundle_readme_includes_anim_latest_token_and_reload_inputs() -> None:
    diag = _make_anim_diag(token="tok-readme", reload_inputs=["npz", "road_csv"])

    text = _build_send_bundle_readme(diag)

    assert "SEND BUNDLE (for chat)" in text
    assert "anim_latest_visual_cache_token: tok-readme" in text
    assert "anim_latest_visual_reload_inputs: npz, road_csv" in text
    assert "anim_latest_global_pointer_json: /abs/workspace/_pointers/anim_latest.json" in text
    assert "triage/latest_anim_pointer_diagnostics.json" in text
    assert "triage/latest_anim_pointer_diagnostics.md" in text



def test_sources_wire_anim_latest_diagnostics_into_triage_and_readme() -> None:
    triage_text = (ROOT / "pneumo_solver_ui" / "tools" / "triage_report.py").read_text(encoding="utf-8")
    bundle_text = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")

    assert '_load_anim_latest_summary' in triage_text
    assert '"anim_latest": anim_summary' in triage_text
    assert '## Anim latest diagnostics' in triage_text
    assert 'Latest anim diagnostics json' in triage_text

    assert '_build_send_bundle_readme' in bundle_text
    assert 'anim_latest_visual_cache_token' in bundle_text
    assert 'triage/latest_anim_pointer_diagnostics.json' in bundle_text
    assert 'readme = _build_send_bundle_readme(anim_diag_event)' in bundle_text
