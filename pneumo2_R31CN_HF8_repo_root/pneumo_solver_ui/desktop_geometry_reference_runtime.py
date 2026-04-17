from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from pneumo_solver_ui.desktop_geometry_reference_model import (
    ArtifactReferenceContext,
    ComponentPassportCatalogRow,
    CylinderCatalogRow,
    CylinderFamilyReferenceRow,
    CylinderMatchRecommendation,
    CylinderPackageReferenceRow,
    CylinderPrechargeReferenceRow,
    ComponentFitReferenceRow,
    GeometryAcceptanceEvidenceSnapshot,
    GeometryReferenceSnapshot,
    PackagingPassportEvidenceSnapshot,
    ParameterGuideRow,
    RoadWidthEvidence,
    RoadWidthReference,
    SpringReferenceSnapshot,
    build_artifact_reference_context,
    build_geometry_acceptance_evidence,
    build_geometry_acceptance_evidence_from_artifact,
    build_component_fit_reference_rows,
    build_cylinder_match_recommendations,
    build_current_cylinder_package_rows,
    build_current_cylinder_precharge_rows,
    build_current_cylinder_reference_rows,
    build_current_spring_reference_snapshot,
    build_cylinder_pressure_estimate,
    build_geometry_reference_diagnostics_handoff,
    build_geometry_reference_snapshot,
    build_packaging_passport_evidence,
    build_parameter_guide_rows,
    build_road_width_evidence,
    build_road_width_reference,
    load_component_passport_catalog_rows,
    load_camozzi_catalog_rows,
)
from pneumo_solver_ui.desktop_input_model import (
    default_base_json_path,
    load_base_with_defaults,
)
from pneumo_solver_ui.anim_export_contract import CYLINDER_PACKAGING_PASSPORT_JSON_NAME
from pneumo_solver_ui.geometry_acceptance_contract import GEOMETRY_ACCEPTANCE_JSON_NAME
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.workspace_contract import resolve_effective_workspace_dir


GEOMETRY_REFERENCE_EVIDENCE_FILENAME = "geometry_reference_evidence.json"
GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME = "latest_geometry_reference_evidence.json"


def _normalize_search_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").replace("_", " ").split())


def _path_identity(value: str | Path | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).expanduser().resolve(strict=False)).casefold()
    except Exception:
        return text.casefold()


def _json_ready(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f".{target.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(target)
    return target


class DesktopGeometryReferenceRuntime:
    def __init__(self, *, ui_root: Path | None = None) -> None:
        self.ui_root = Path(ui_root or Path(__file__).resolve().parent).resolve()
        self.base_path = default_base_json_path()
        self.component_passport_path = self.ui_root / "component_passport.json"
        self._catalog_rows = load_camozzi_catalog_rows()

    def resolve_base_path(self, raw_path: str | Path | None = None) -> Path:
        if raw_path is None:
            return Path(self.base_path).resolve()
        text = str(raw_path).strip()
        if not text:
            return Path(self.base_path).resolve()
        return Path(text).expanduser().resolve()

    def describe_base_source(self, raw_path: str | Path | None = None) -> str:
        path = self.resolve_base_path(raw_path)
        if path == default_base_json_path():
            return f"default_base.json: {path}"
        if path.exists():
            return f"overlay base: {path}"
        return f"overlay не найден, используются defaults: {path}"

    def load_base_payload(self, raw_path: str | Path | None = None) -> dict[str, Any]:
        path = self.resolve_base_path(raw_path)
        return load_base_with_defaults(path)

    def geometry_snapshot(
        self,
        raw_path: str | Path | None = None,
        *,
        dw_min_mm: float = -100.0,
        dw_max_mm: float = 100.0,
        sample_count: int = 81,
    ) -> GeometryReferenceSnapshot:
        path = self.resolve_base_path(raw_path)
        return build_geometry_reference_snapshot(
            self.load_base_payload(path),
            base_path=path,
            dw_min_mm=dw_min_mm,
            dw_max_mm=dw_max_mm,
            sample_count=sample_count,
        )

    def current_cylinder_rows(
        self,
        raw_path: str | Path | None = None,
    ) -> tuple[CylinderFamilyReferenceRow, ...]:
        return build_current_cylinder_reference_rows(self.load_base_payload(raw_path))

    def current_cylinder_precharge_rows(
        self,
        raw_path: str | Path | None = None,
    ) -> tuple[CylinderPrechargeReferenceRow, ...]:
        return build_current_cylinder_precharge_rows(self.load_base_payload(raw_path))

    def current_cylinder_package_rows(
        self,
        raw_path: str | Path | None = None,
    ) -> tuple[CylinderPackageReferenceRow, ...]:
        return build_current_cylinder_package_rows(self.load_base_payload(raw_path))

    def current_spring_snapshot(
        self,
        raw_path: str | Path | None = None,
    ) -> SpringReferenceSnapshot:
        return build_current_spring_reference_snapshot(self.load_base_payload(raw_path))

    def component_fit_rows(
        self,
        raw_path: str | Path | None = None,
        *,
        dw_min_mm: float = -100.0,
        dw_max_mm: float = 100.0,
    ) -> tuple[ComponentFitReferenceRow, ...]:
        path = self.resolve_base_path(raw_path)
        return build_component_fit_reference_rows(
            self.load_base_payload(path),
            base_path=path,
            dw_min_mm=dw_min_mm,
            dw_max_mm=dw_max_mm,
        )

    def component_passport_rows(
        self,
        passport_path: str | Path | None = None,
    ) -> tuple[ComponentPassportCatalogRow, ...]:
        return load_component_passport_catalog_rows(passport_path or self.component_passport_path)

    def road_width_reference(
        self,
        raw_path: str | Path | None = None,
    ) -> RoadWidthReference:
        return build_road_width_reference(self.load_base_payload(raw_path))

    def geometry_acceptance_evidence(
        self,
        frame_or_mapping: Any | None = None,
        *,
        source_label: str = "",
        tol_m: float = 1e-6,
    ) -> GeometryAcceptanceEvidenceSnapshot:
        return build_geometry_acceptance_evidence(
            frame_or_mapping,
            source_label=source_label,
            tol_m=tol_m,
        )

    def _artifact_summary_from_path(self, raw_path: str | Path | None) -> dict[str, Any]:
        text = str(raw_path or "").strip()
        if not text:
            return {}
        try:
            path = Path(text).expanduser().resolve(strict=False)
        except Exception:
            path = Path(text)
        exists = False
        try:
            exists = bool(path.exists())
        except Exception:
            exists = False
        suffix = path.suffix.lower()
        if suffix == ".npz":
            return {
                "source_label": f"selected artifact: {path}",
                "anim_latest_usable": bool(exists),
                "anim_latest_npz_path": str(path),
                "anim_latest_npz_exists": bool(exists),
                "anim_latest_npz_in_workspace": False,
                "anim_latest_cylinder_packaging_passport_path": str(path.parent / CYLINDER_PACKAGING_PASSPORT_JSON_NAME),
                "anim_latest_cylinder_packaging_passport_exists": bool((path.parent / CYLINDER_PACKAGING_PASSPORT_JSON_NAME).exists()),
                "anim_latest_geometry_acceptance_json_path": str(path.parent / GEOMETRY_ACCEPTANCE_JSON_NAME),
                "anim_latest_geometry_acceptance_json_exists": bool((path.parent / GEOMETRY_ACCEPTANCE_JSON_NAME).exists()),
                "anim_latest_issues": [] if exists else [f"selected NPZ artifact is missing on disk: {path}"],
            }

        pointer_obj: dict[str, Any] = {}
        if exists:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                pointer_obj = dict(loaded) if isinstance(loaded, dict) else {}
            except Exception:
                pointer_obj = {}
        raw_npz = (
            pointer_obj.get("npz_path")
            or pointer_obj.get("anim_latest_npz")
            or pointer_obj.get("anim_latest_npz_path")
            or ""
        )
        npz_path = ""
        if str(raw_npz or "").strip():
            try:
                npz_candidate = Path(str(raw_npz)).expanduser()
                if not npz_candidate.is_absolute():
                    npz_candidate = path.parent / npz_candidate
                npz_path = str(npz_candidate.resolve(strict=False))
            except Exception:
                npz_path = str(raw_npz)
        npz_exists = bool(Path(npz_path).exists()) if npz_path else False
        meta = pointer_obj.get("meta") if isinstance(pointer_obj.get("meta"), dict) else pointer_obj.get("anim_latest_meta")
        artifact_dir = Path(npz_path).parent if npz_path else path.parent
        return {
            "source_label": f"selected artifact pointer: {path}",
            "anim_latest_usable": bool(exists and npz_exists),
            "anim_latest_pointer_json": str(path),
            "anim_latest_pointer_json_exists": bool(exists),
            "anim_latest_pointer_json_in_workspace": False,
            "anim_latest_npz_path": npz_path,
            "anim_latest_npz_exists": bool(npz_exists) if npz_path else None,
            "anim_latest_npz_in_workspace": False if npz_path else None,
            "anim_latest_updated_utc": str(pointer_obj.get("updated_utc") or pointer_obj.get("updated_at") or ""),
            "anim_latest_visual_cache_token": str(pointer_obj.get("visual_cache_token") or ""),
            "anim_latest_meta": dict(meta or {}) if isinstance(meta, dict) else {},
            "anim_latest_cylinder_packaging_passport_path": str(artifact_dir / CYLINDER_PACKAGING_PASSPORT_JSON_NAME),
            "anim_latest_cylinder_packaging_passport_exists": bool((artifact_dir / CYLINDER_PACKAGING_PASSPORT_JSON_NAME).exists()),
            "anim_latest_geometry_acceptance_json_path": str(artifact_dir / GEOMETRY_ACCEPTANCE_JSON_NAME),
            "anim_latest_geometry_acceptance_json_exists": bool((artifact_dir / GEOMETRY_ACCEPTANCE_JSON_NAME).exists()),
            "anim_latest_issues": [] if exists and (not npz_path or npz_exists) else [
                f"selected artifact pointer/NPZ is stale: {path}"
            ],
        }

    def artifact_context(
        self,
        summary: dict[str, Any] | None = None,
        *,
        artifact_path: str | Path | None = None,
    ) -> ArtifactReferenceContext:
        if artifact_path not in (None, ""):
            summary = self._artifact_summary_from_path(artifact_path)
        elif summary is None:
            try:
                summary = collect_anim_latest_diagnostics_summary(include_meta=True)
            except Exception:
                summary = {}
        return build_artifact_reference_context(summary)

    def artifact_geometry_acceptance_evidence(
        self,
        artifact_context: ArtifactReferenceContext | None = None,
        *,
        summary: dict[str, Any] | None = None,
        artifact_path: str | Path | None = None,
        tol_m: float = 1e-6,
    ) -> GeometryAcceptanceEvidenceSnapshot:
        artifact = artifact_context or self.artifact_context(summary, artifact_path=artifact_path)
        return build_geometry_acceptance_evidence_from_artifact(artifact, tol_m=tol_m)

    def road_width_evidence(
        self,
        raw_path: str | Path | None = None,
        *,
        artifact_context: ArtifactReferenceContext | None = None,
        summary: dict[str, Any] | None = None,
    ) -> RoadWidthEvidence:
        artifact = artifact_context or self.artifact_context(summary)
        return build_road_width_evidence(
            self.load_base_payload(raw_path),
            artifact_meta=artifact.meta,
        )

    def packaging_passport_evidence(
        self,
        raw_path: str | Path | None = None,
        *,
        artifact_context: ArtifactReferenceContext | None = None,
        summary: dict[str, Any] | None = None,
    ) -> PackagingPassportEvidenceSnapshot:
        artifact = artifact_context or self.artifact_context(summary)
        return build_packaging_passport_evidence(
            self.current_cylinder_package_rows(raw_path),
            artifact_context=artifact,
        )

    def diagnostics_handoff_evidence(
        self,
        raw_path: str | Path | None = None,
        *,
        artifact_context: ArtifactReferenceContext | None = None,
        artifact_path: str | Path | None = None,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact = artifact_context or self.artifact_context(summary, artifact_path=artifact_path)
        payload = build_geometry_reference_diagnostics_handoff(
            artifact_context=artifact,
            component_rows=self.component_passport_rows(),
            road_width=self.road_width_evidence(raw_path, artifact_context=artifact),
            packaging=self.packaging_passport_evidence(raw_path, artifact_context=artifact),
            acceptance=self.artifact_geometry_acceptance_evidence(artifact),
        )
        freshness = self.artifact_freshness_evidence(
            artifact_context=artifact,
            artifact_path=artifact_path,
        )
        payload.update(
            {
                "artifact_freshness_status": freshness["status"],
                "artifact_freshness_relation": freshness["relation"],
                "artifact_freshness_reason": freshness["reason"],
                "latest_artifact_status": freshness["latest_status"],
                "latest_artifact_npz_path": freshness["latest_npz_path"],
                "latest_artifact_pointer_path": freshness["latest_pointer_path"],
                "latest_artifact_updated_utc": freshness["latest_updated_utc"],
                "selected_artifact_npz_path": freshness["selected_npz_path"],
                "selected_artifact_pointer_path": freshness["selected_pointer_path"],
            }
        )
        return payload

    def artifact_freshness_evidence(
        self,
        artifact_context: ArtifactReferenceContext | None = None,
        *,
        artifact_path: str | Path | None = None,
        latest_context: ArtifactReferenceContext | None = None,
        latest_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected_path = str(artifact_path or "").strip()
        selected = artifact_context or self.artifact_context(artifact_path=selected_path)
        latest = selected if not selected_path and latest_context is None else (
            latest_context or self.artifact_context(latest_summary)
        )
        issues = list(selected.issues)

        selected_npz_id = _path_identity(selected.npz_path)
        latest_npz_id = _path_identity(latest.npz_path)
        selected_pointer_id = _path_identity(selected.pointer_path)
        latest_pointer_id = _path_identity(latest.pointer_path)
        matches_npz = bool(selected_npz_id and latest_npz_id and selected_npz_id == latest_npz_id)
        matches_pointer = bool(
            selected_pointer_id and latest_pointer_id and selected_pointer_id == latest_pointer_id
        )

        if not selected_path:
            status = selected.status
            relation = "latest"
            reason = "Using latest artifact helper; no selected artifact override."
        elif selected.status in {"missing", "stale"}:
            status = selected.status
            relation = "selected_unavailable"
            reason = "Selected artifact pointer/NPZ is unavailable or stale."
        elif latest.status == "missing":
            status = "historical"
            relation = "selected_without_latest"
            reason = "Selected artifact is readable, but latest artifact context is missing."
        elif matches_npz or matches_pointer:
            status = "current"
            relation = "matches_latest"
            reason = "Selected artifact matches latest by NPZ or pointer path."
        else:
            status = "historical"
            relation = "differs_from_latest"
            reason = "Selected artifact is readable, but differs from the current latest artifact."
            issues.append(
                "selected NPZ differs from latest NPZ: "
                f"{selected.npz_path or '—'} vs {latest.npz_path or '—'}"
            )

        return {
            "status": status,
            "relation": relation,
            "reason": reason,
            "selected_status": selected.status,
            "latest_status": latest.status,
            "selected_source_label": selected.source_label,
            "latest_source_label": latest.source_label,
            "selected_pointer_path": selected.pointer_path,
            "latest_pointer_path": latest.pointer_path,
            "selected_npz_path": selected.npz_path,
            "latest_npz_path": latest.npz_path,
            "selected_updated_utc": selected.updated_utc,
            "latest_updated_utc": latest.updated_utc,
            "selected_visual_cache_token": selected.visual_cache_token,
            "latest_visual_cache_token": latest.visual_cache_token,
            "issues": list(dict.fromkeys(str(item) for item in issues if str(item or "").strip())),
        }

    def write_diagnostics_handoff_evidence(
        self,
        raw_path: str | Path | None = None,
        *,
        artifact_context: ArtifactReferenceContext | None = None,
        artifact_path: str | Path | None = None,
        summary: dict[str, Any] | None = None,
        exports_dir: str | Path | None = None,
        send_bundles_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        payload = _json_ready(
            self.diagnostics_handoff_evidence(
                raw_path,
                artifact_context=artifact_context,
                artifact_path=artifact_path,
                summary=summary,
            )
        )
        repo_root = self.ui_root.parent.resolve()
        if exports_dir is None:
            workspace_dir = resolve_effective_workspace_dir(repo_root)
            workspace_path = workspace_dir / "exports" / GEOMETRY_REFERENCE_EVIDENCE_FILENAME
        else:
            workspace_path = Path(exports_dir).expanduser().resolve() / GEOMETRY_REFERENCE_EVIDENCE_FILENAME
        if send_bundles_dir is None:
            sidecar_path = repo_root / "send_bundles" / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME
        else:
            sidecar_path = Path(send_bundles_dir).expanduser().resolve() / GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME

        written_workspace = _atomic_write_json(workspace_path, payload)
        written_sidecar = _atomic_write_json(sidecar_path, payload)
        return {
            "payload": payload,
            "workspace_path": written_workspace,
            "sidecar_path": written_sidecar,
            "workspace_arcname": f"workspace/exports/{GEOMETRY_REFERENCE_EVIDENCE_FILENAME}",
            "sidecar_name": GEOMETRY_REFERENCE_EVIDENCE_SIDECAR_NAME,
        }

    def catalog_variant_labels(self) -> tuple[str, ...]:
        labels = sorted({row.variant_label for row in self._catalog_rows})
        return tuple(labels)

    def cylinder_catalog_rows(
        self,
        *,
        variant_label: str = "",
        search_query: str = "",
    ) -> tuple[CylinderCatalogRow, ...]:
        rows = self._catalog_rows
        if variant_label and variant_label != "Все варианты":
            rows = tuple(row for row in rows if row.variant_label == variant_label)
        query = _normalize_search_text(search_query)
        if not query:
            return rows
        tokens = tuple(token for token in query.split(" ") if token)
        filtered: list[CylinderCatalogRow] = []
        for row in rows:
            haystack = _normalize_search_text(
                " ".join(
                    (
                        row.variant_label,
                        row.variant_key,
                        str(row.bore_mm),
                        str(row.rod_mm),
                        row.port_thread,
                        row.rod_thread,
                        str(row.B_mm),
                        str(row.E_mm),
                        str(row.TG_mm),
                    )
                )
            )
            if all(token in haystack for token in tokens):
                filtered.append(row)
        return tuple(filtered)

    def cylinder_pressure_summary(
        self,
        row: CylinderCatalogRow | CylinderFamilyReferenceRow,
        pressure_bar_gauge: float,
    ):
        return build_cylinder_pressure_estimate(row, pressure_bar_gauge)

    def cylinder_match_recommendations(
        self,
        family: str,
        *,
        raw_path: str | Path | None = None,
        variant_label: str = "",
        search_query: str = "",
        limit: int = 5,
    ) -> tuple[CylinderMatchRecommendation, ...]:
        current_rows = {row.family: row for row in self.current_cylinder_rows(raw_path)}
        current_precharge_rows = {row.family: row for row in self.current_cylinder_precharge_rows(raw_path)}
        current_row = current_rows.get(str(family or "").strip())
        if current_row is None:
            return ()
        return build_cylinder_match_recommendations(
            current_row,
            self.cylinder_catalog_rows(
                variant_label=variant_label,
                search_query=search_query,
            ),
            current_precharge=current_precharge_rows.get(str(family or "").strip()),
            limit=limit,
        )

    def parameter_guide_rows(
        self,
        query: str = "",
        *,
        raw_path: str | Path | None = None,
        limit: int = 80,
    ) -> tuple[ParameterGuideRow, ...]:
        return build_parameter_guide_rows(
            query,
            base_payload=self.load_base_payload(raw_path),
            limit=limit,
        )


__all__ = [
    "DesktopGeometryReferenceRuntime",
]
