from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from pneumo_solver_ui.ui_interaction_helpers import strip_svg_xml_header


DEFAULT_SVG_VIEWBOX = "0 0 1920 1080"
DEFAULT_SVG_PRESSURE_NODES = (
    "Ресивер1",
    "Ресивер2",
    "Ресивер3",
    "Аккумулятор",
    "узел_после_рег_Pmin_питание_Р2",
    "узел_после_предохран_Pmax",
    "узел_после_рег_Pmid",
    "узел_после_рег_Pmin_сброс",
    "узел_после_рег_заряд_аккумулятора",
    "Магистраль_ЛП2_ПЗ2",
    "Магистраль_ПП2_ЛЗ2",
)


def render_svg_click_mode_selector(st_module, *, key: str = "svg_click_mode") -> str:
    return st_module.radio(
        "Клик по схеме",
        options=["add", "replace"],
        format_func=lambda value: "Добавлять к выбору" if value == "add" else "Заменять выбор",
        horizontal=True,
        key=key,
    )


def svg_edge_columns(df_mdot: Any) -> list[str]:
    if df_mdot is None:
        return []
    return [column for column in df_mdot.columns if column != "время_с"]


def svg_pressure_node_columns(df_p: Any) -> list[str]:
    if df_p is None:
        return []
    return [column for column in df_p.columns if column != "время_с"]


def default_svg_pressure_nodes(node_columns: Sequence[str], *, limit: int = 8) -> list[str]:
    node_columns = list(node_columns)
    defaults = [name for name in DEFAULT_SVG_PRESSURE_NODES if name in node_columns]
    if defaults:
        return defaults
    return node_columns[: min(limit, len(node_columns))]


def render_svg_pressure_node_selector(
    st_module,
    node_columns: Sequence[str],
    *,
    key: str = "anim_nodes_svg",
) -> list[str]:
    node_columns = list(node_columns)
    if not node_columns:
        st_module.info("Подписи давления на схеме доступны только при record_full=True (df_p).")
        return []
    return st_module.multiselect(
        "Узлы давления для отображения на схеме",
        options=node_columns,
        default=default_svg_pressure_nodes(node_columns),
        key=key,
    )


def read_svg_text(default_svg_path: Path, uploaded_file: Any | None) -> str:
    default_svg_text = ""
    if default_svg_path.exists():
        try:
            default_svg_text = default_svg_path.read_text(encoding="utf-8")
        except Exception:
            default_svg_text = default_svg_path.read_text(errors="ignore")
    if uploaded_file is None:
        return default_svg_text
    try:
        return uploaded_file.getvalue().decode("utf-8")
    except Exception:
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")


def extract_svg_viewbox(svg_inline: str, *, default: str = DEFAULT_SVG_VIEWBOX) -> str:
    match = re.search(r'viewBox\s*=\s*"([^"]+)"', svg_inline)
    if match:
        return match.group(1)
    return default


def build_svg_mapping_template(
    *,
    svg_inline: str,
    edge_columns: Sequence[str],
    selected_node_names: Sequence[str],
) -> dict[str, object]:
    return {
        "version": 2,
        "viewBox": extract_svg_viewbox(svg_inline),
        "edges": {name: [] for name in edge_columns},
        "nodes": {name: None for name in selected_node_names},
    }


def render_svg_source_template_controls(
    st_module,
    *,
    base_dir: Path,
    edge_columns: Sequence[str],
    selected_node_names: Sequence[str],
    uploader_key: str = "svg_scheme_upl",
) -> tuple[str | None, str | None]:
    default_svg_path = base_dir / "assets" / "pneumo_scheme.svg"
    svg_upload = st_module.file_uploader(
        "SVG файл схемы (опционально, если хотите заменить)",
        type=["svg"],
        key=uploader_key,
    )
    svg_text = read_svg_text(default_svg_path, svg_upload)
    if not svg_text:
        st_module.warning("SVG не найден. Положите файл в assets/pneumo_scheme.svg или загрузите через uploader.")
        return None, None

    svg_inline = strip_svg_xml_header(svg_text)
    template_mapping = build_svg_mapping_template(
        svg_inline=svg_inline,
        edge_columns=edge_columns,
        selected_node_names=selected_node_names,
    )
    st_module.download_button(
        "Скачать шаблон mapping JSON",
        data=json.dumps(template_mapping, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="pneumo_svg_mapping_template.json",
        mime="application/json",
    )
    return svg_text, svg_inline
