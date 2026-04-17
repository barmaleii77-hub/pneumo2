from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.tools.knowledge_base_sync import (
    add_chat_plan,
    add_chat_requirement,
    knowledge_base_tracked_paths,
    load_knowledge_base_store,
    render_chat_plans_markdown,
    render_chat_requirements_markdown,
    save_knowledge_base_store,
)


ROOT = Path(__file__).resolve().parents[1]


def test_chat_knowledge_base_store_exists_and_is_seeded() -> None:
    path = ROOT / "docs" / "15_CHAT_KNOWLEDGE_BASE.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema"] == "pneumo.chat_knowledge_base.v1"
    assert len(data["requirements"]) >= 9
    assert len(data["plans"]) >= 15
    assert any("GUI" in item["title"] or "desktop" in item["details"].lower() for item in data["requirements"])
    assert any(item["artifact_path"] == "gui_chat_prompts/08_OPTIMIZER_CENTER.md" for item in data["plans"])
    assert any(
        item["title"] == "Release-gate closure must stay evidence-mapped before runtime closure claims."
        for item in data["requirements"]
    )
    assert any(
        item["title"] == "Dirty release-readiness worktree must be partitioned by V32 lane before staging."
        for item in data["requirements"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"] == "context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"] == "context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )
    assert any(
        item["artifact_path"]
        == "context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md"
        for item in data["plans"]
    )


def test_chat_knowledge_base_adders_dedupe_same_entry() -> None:
    store = {"schema": "x", "updated_at": "x", "requirements": [], "plans": []}

    added_first = add_chat_requirement(
        store,
        title="Все хотелки из чатов должны попадать в базу знаний.",
        details="Статус: активно.",
    )
    added_second = add_chat_requirement(
        store,
        title="Все хотелки из чатов должны попадать в базу знаний.",
        details="Статус: активно.",
    )
    assert added_first is True
    assert added_second is False
    assert len(store["requirements"]) == 1

    added_plan_first = add_chat_plan(
        store,
        title="gui_chat_prompts/05_COMPARE_VIEWER.md",
        details="Compare viewer.",
        artifact_path="gui_chat_prompts/05_COMPARE_VIEWER.md",
    )
    added_plan_second = add_chat_plan(
        store,
        title="gui_chat_prompts/05_COMPARE_VIEWER.md",
        details="Compare viewer.",
        artifact_path="gui_chat_prompts/05_COMPARE_VIEWER.md",
    )
    assert added_plan_first is True
    assert added_plan_second is False
    assert len(store["plans"]) == 1


def test_chat_knowledge_base_renderers_emit_operator_facing_logs() -> None:
    store = {
        "schema": "pneumo.chat_knowledge_base.v1",
        "updated_at": "2026-04-13T00:00:00+00:00",
        "requirements": [
            {
                "id": "REQ-0001",
                "created_at": "2026-04-13T00:00:00+00:00",
                "source": "chat",
                "title": "GUI должен быть главным направлением.",
                "details": "WEB использовать только как reference.",
                "status": "активно",
            }
        ],
        "plans": [
            {
                "id": "PLAN-0001",
                "created_at": "2026-04-13T00:00:00+00:00",
                "source": "chat",
                "title": "gui_chat_prompts/01_MAIN_WINDOW.md",
                "details": "Главное окно приложения.",
                "artifact_path": "gui_chat_prompts/01_MAIN_WINDOW.md",
                "status": "актуален",
            }
        ],
    }

    req_md = render_chat_requirements_markdown(store)
    plan_md = render_chat_plans_markdown(store)

    assert "knowledge_base_sync" in req_md
    assert "GUI должен быть главным направлением." in req_md
    assert "ID: `REQ-0001`." in req_md

    assert "knowledge_base_sync" in plan_md
    assert "gui_chat_prompts/01_MAIN_WINDOW.md" in plan_md
    assert "Артефакт: [gui_chat_prompts/01_MAIN_WINDOW.md]" in plan_md
    assert "ID: `PLAN-0001`." in plan_md


def test_chat_knowledge_base_store_roundtrip_uses_docs_folder() -> None:
    temp_root = ROOT / "workspace" / "tmp_kb_contract_root"
    docs_dir = temp_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    store = {
        "schema": "pneumo.chat_knowledge_base.v1",
        "updated_at": "x",
        "requirements": [],
        "plans": [],
    }
    save_knowledge_base_store(store, temp_root)
    loaded = load_knowledge_base_store(temp_root)

    assert loaded["schema"] == "pneumo.chat_knowledge_base.v1"
    assert (docs_dir / "15_CHAT_KNOWLEDGE_BASE.json").exists()


def test_chat_knowledge_base_tracked_paths_cover_main_docs() -> None:
    tracked = {path.name for path in knowledge_base_tracked_paths(ROOT)}

    assert "00_PROJECT_KNOWLEDGE_BASE.md" in tracked
    assert "13_CHAT_REQUIREMENTS_LOG.md" in tracked
    assert "14_CHAT_PLANS_LOG.md" in tracked
    assert "15_CHAT_KNOWLEDGE_BASE.json" in tracked
