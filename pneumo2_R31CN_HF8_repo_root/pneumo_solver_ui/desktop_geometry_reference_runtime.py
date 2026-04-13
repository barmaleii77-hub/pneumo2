from __future__ import annotations

from pathlib import Path
from typing import Any

from pneumo_solver_ui.desktop_geometry_reference_model import (
    CylinderCatalogRow,
    CylinderFamilyReferenceRow,
    CylinderMatchRecommendation,
    CylinderPackageReferenceRow,
    CylinderPrechargeReferenceRow,
    ComponentFitReferenceRow,
    GeometryReferenceSnapshot,
    ParameterGuideRow,
    SpringReferenceSnapshot,
    build_component_fit_reference_rows,
    build_cylinder_match_recommendations,
    build_current_cylinder_package_rows,
    build_current_cylinder_precharge_rows,
    build_current_cylinder_reference_rows,
    build_current_spring_reference_snapshot,
    build_cylinder_pressure_estimate,
    build_geometry_reference_snapshot,
    build_parameter_guide_rows,
    load_camozzi_catalog_rows,
)
from pneumo_solver_ui.desktop_input_model import (
    default_base_json_path,
    load_base_with_defaults,
)


def _normalize_search_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").replace("_", " ").split())


class DesktopGeometryReferenceRuntime:
    def __init__(self, *, ui_root: Path | None = None) -> None:
        self.ui_root = Path(ui_root or Path(__file__).resolve().parent).resolve()
        self.base_path = default_base_json_path()
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
