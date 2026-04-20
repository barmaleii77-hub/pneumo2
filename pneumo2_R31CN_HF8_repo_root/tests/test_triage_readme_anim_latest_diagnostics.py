from __future__ import annotations

import json
import os
from pathlib import Path

from pneumo_solver_ui.tools.make_send_bundle import _build_send_bundle_readme
from pneumo_solver_ui.tools.send_bundle_contract import ANIM_DIAG_JSON, ANIM_DIAG_MD, ANIM_DIAG_SIDECAR_JSON, ANIM_DIAG_SIDECAR_MD
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
        "anim_latest_meta": {
            "road_csv": "anim_latest_road_csv.csv",
            "scenario_kind": "ring",
            "ring_closure_policy": "strict_exact",
            "ring_closure_applied": False,
            "ring_seam_open": True,
            "ring_seam_max_jump_m": 0.012,
            "ring_raw_seam_max_jump_m": 0.015,
        },
        "anim_latest_mnemo_event_log_ref": "anim_latest.desktop_mnemo_events.json",
        "anim_latest_mnemo_event_log_path": "/abs/workspace/exports/anim_latest.desktop_mnemo_events.json",
        "anim_latest_mnemo_event_log_exists": True,
        "anim_latest_mnemo_event_log_schema_version": "desktop_mnemo_event_log_v1",
        "anim_latest_mnemo_event_log_updated_utc": "2026-03-11T12:05:00+00:00",
        "anim_latest_mnemo_event_log_current_mode": "Регуляторный коридор",
        "anim_latest_mnemo_event_log_event_count": 4,
        "anim_latest_mnemo_event_log_active_latch_count": 1,
        "anim_latest_mnemo_event_log_acknowledged_latch_count": 2,
        "anim_latest_mnemo_event_log_recent_titles": ["Большой перепад давлений", "Смена режима"],
    }



def test_generate_triage_report_exposes_anim_latest_diagnostics_from_sidecar(tmp_path: Path) -> None:
    sb_root = tmp_path / "send_bundles"
    sb_root.mkdir(parents=True, exist_ok=True)
    diag = _make_anim_diag(token="tok-triage")
    (sb_root / ANIM_DIAG_SIDECAR_JSON).write_text(
        json.dumps(diag, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (sb_root / ANIM_DIAG_SIDECAR_MD).write_text(
        "# Anim latest diagnostics\n\n- token: tok-triage\n",
        encoding="utf-8",
    )

    md, summary = generate_triage_report(tmp_path, keep_last_n=1)
    anim = dict(summary.get("anim_latest") or {})
    mnemo = dict(summary.get("mnemo_event_log") or {})
    paths = dict(summary.get("paths") or {})

    assert anim["source"] == "send_bundle_sidecar"
    assert anim["anim_latest_available"] is True
    assert anim["anim_latest_visual_cache_token"] == "tok-triage"
    assert anim["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert mnemo["severity"] == "critical"
    assert mnemo["current_mode"] == "Регуляторный коридор"
    assert summary["severity_counts"]["critical"] == 1
    assert summary["severity_counts"]["warn"] >= 1
    assert summary["operator_recommendations"][0].startswith("Сначала откройте мнемосхему")
    assert any("открытый шов кольца ожидаем" in item for item in summary["operator_recommendations"])
    assert any("В мнемосхеме есть активные события: 1" in flag for flag in summary["red_flags"])
    assert any("Шов кольца открыт в режиме strict_exact" in flag for flag in summary["red_flags"])
    assert summary["ring_closure"]["severity"] == "warn"
    assert summary["ring_closure"]["closure_policy"] == "strict_exact"
    assert os.path.normcase(paths["latest_anim_pointer_diagnostics_json"]) == os.path.normcase(str((sb_root / ANIM_DIAG_SIDECAR_JSON).resolve()))
    assert os.path.normcase(paths["latest_anim_pointer_diagnostics_md"]) == os.path.normcase(str((sb_root / ANIM_DIAG_SIDECAR_MD).resolve()))
    assert "## События мнемосхемы" in md
    assert "## Рекомендуемые действия" in md
    assert "Регуляторный коридор" in md
    assert "Большой перепад давлений" in md
    assert "## Последняя анимация" in md
    assert "tok-triage" in md
    assert "npz, road_csv" in md
    assert "Тип сценария: `ring`" in md
    assert "Замыкание кольца: режим=`strict_exact` / применено=`False` / шов открыт=`True` / скачок шва, м=`0.012` / исходный скачок, м=`0.015`" in md
    assert "Данные последней анимации, JSON" in md



def test_build_send_bundle_readme_includes_anim_latest_token_and_reload_inputs() -> None:
    diag = _make_anim_diag(token="tok-readme", reload_inputs=["npz", "road_csv"])

    text = _build_send_bundle_readme(diag)

    assert "АРХИВ ПРОЕКТА" in text
    assert "Токен визуального кэша: tok-readme" in text
    assert "Входные данные перезагрузки: npz, road_csv" in text
    assert "Тип сценария: ring" in text
    assert "Замыкание кольца: режим=strict_exact / применено=False / шов открыт=True / скачок шва, м=0.012 / исходный скачок, м=0.015" in text
    assert "Рекомендуемые действия:" in text
    assert "Сначала откройте мнемосхему" in text
    assert "Общий указатель: /abs/workspace/_pointers/anim_latest.json" in text
    assert ANIM_DIAG_JSON in text
    assert ANIM_DIAG_MD in text



def test_sources_wire_anim_latest_diagnostics_into_triage_and_readme() -> None:
    triage_text = (ROOT / "pneumo_solver_ui" / "tools" / "triage_report.py").read_text(encoding="utf-8")
    bundle_text = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")

    assert '_load_anim_latest_summary' in triage_text
    assert '"anim_latest": anim_summary' in triage_text
    assert '## Последняя анимация' in triage_text
    assert 'Тип сценария' in triage_text
    assert 'Замыкание кольца' in triage_text
    assert '## События мнемосхемы' in triage_text
    assert '"mnemo_event_log": mnemo_event_summary' in triage_text
    assert '"operator_recommendations": operator_recommendations' in triage_text
    assert '## Рекомендуемые действия' in triage_text
    assert 'ANIM_DIAG_SIDECAR_JSON' in triage_text
    assert 'ANIM_DIAG_SIDECAR_MD' in triage_text

    assert '_build_send_bundle_readme' in bundle_text
    assert 'anim_latest_visual_cache_token' in bundle_text
    assert 'Тип сценария:' in bundle_text
    assert 'Замыкание кольца: режим=' in bundle_text
    assert 'ANIM_DIAG_JSON' in bundle_text
    assert 'ANIM_DIAG_MD' in bundle_text
    assert 'readme = _build_send_bundle_readme(anim_diag_event)' in bundle_text
