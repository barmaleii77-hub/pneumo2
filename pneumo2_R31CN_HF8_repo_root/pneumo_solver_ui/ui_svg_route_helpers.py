from __future__ import annotations

import json
import re
from typing import Iterable


SVG_ROUTE_LATINIZE_TABLE = str.maketrans(
    {
        "Л": "L",
        "П": "P",
        "З": "Z",
        "л": "l",
        "п": "p",
        "з": "z",
        "Р": "R",
        "р": "r",
        "В": "B",
        "в": "b",
        "А": "A",
        "а": "a",
        "Е": "E",
        "е": "e",
        "К": "K",
        "к": "k",
        "М": "M",
        "м": "m",
        "Н": "H",
        "н": "h",
        "О": "O",
        "о": "o",
        "С": "C",
        "с": "c",
        "Т": "T",
        "т": "t",
        "У": "Y",
        "у": "y",
        "Х": "X",
        "х": "x",
    }
)


def is_noise_svg_route_label(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    text_upper = text.upper()
    if text_upper in {"P", "Q", "PQ", "PQPQ"}:
        return True
    if len(text) == 1:
        return True
    return False


def build_svg_route_label_items(
    texts: Iterable[object],
    *,
    filter_text: str = "",
    limit: int = 600,
) -> list[tuple[int, str, float, float]]:
    items: list[tuple[int, str, float, float]] = []
    filter_text = (filter_text or "").strip().lower()
    for text_index, text_item in enumerate(texts):
        try:
            label = str(text_item.get("text", "")).strip()
            if is_noise_svg_route_label(label):
                continue
            if filter_text and filter_text not in label.lower():
                continue
            x_coord = float(text_item.get("x", 0.0))
            y_coord = float(text_item.get("y", 0.0))
            items.append((text_index, label, x_coord, y_coord))
        except Exception:
            continue
    return items[:limit]


def format_svg_route_item(item: tuple[int, str, float, float]) -> str:
    text_index, label, x_coord, y_coord = item
    return f"#{text_index:03d} | {label} | ({x_coord:.0f},{y_coord:.0f})"


def latinize_svg_route_signature(text: object) -> str:
    try:
        return str(text).translate(SVG_ROUTE_LATINIZE_TABLE)
    except Exception:
        return str(text)


def score_svg_route_edge_label(edge_name: str, label: str, *, name_score_fn) -> float:
    try:
        score_direct = name_score_fn(edge_name, label)
        score_latinized = name_score_fn(
            latinize_svg_route_signature(edge_name),
            latinize_svg_route_signature(label),
        )
        return float(max(score_direct, score_latinized))
    except Exception:
        return 0.0


def build_svg_route_candidates(
    items: Iterable[tuple[int, str, float, float]],
    edge_name: str,
    *,
    min_score: float,
    top_k: int,
    name_score_fn,
) -> list[tuple[float, tuple[int, str, float, float]]]:
    candidates: list[tuple[float, tuple[int, str, float, float]]] = []
    for item in items:
        _, label, _, _ = item
        score_value = score_svg_route_edge_label(edge_name, str(label), name_score_fn=name_score_fn)
        if score_value >= float(min_score):
            candidates.append((float(score_value), item))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[: int(top_k)]


def choose_svg_route_candidate_pair(
    candidates: list[tuple[float, tuple[int, str, float, float]]],
    strategy: str,
):
    if not candidates or len(candidates) < 2:
        return None
    if strategy == "Top2":
        return candidates[0], candidates[1]
    if strategy == "Best+Farthest":
        best = candidates[0]
        best_x = float(best[1][2])
        best_y = float(best[1][3])
        best_index = 1
        best_distance = -1.0
        for index in range(1, len(candidates)):
            item = candidates[index]
            x_coord = float(item[1][2])
            y_coord = float(item[1][3])
            distance = (x_coord - best_x) ** 2 + (y_coord - best_y) ** 2
            if distance > best_distance:
                best_distance = distance
                best_index = index
        return best, candidates[best_index]
    best_pair = (candidates[0], candidates[1])
    best_distance = -1.0
    best_score_sum = -1.0
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            x_i = float(candidates[i][1][2])
            y_i = float(candidates[i][1][3])
            x_j = float(candidates[j][1][2])
            y_j = float(candidates[j][1][3])
            distance = (x_i - x_j) ** 2 + (y_i - y_j) ** 2
            score_sum = float(candidates[i][0]) + float(candidates[j][0])
            if distance > best_distance or (abs(distance - best_distance) < 1e-9 and score_sum > best_score_sum):
                best_distance = distance
                best_score_sum = score_sum
                best_pair = (candidates[i], candidates[j])
    return best_pair


def build_svg_route_options(
    items: Iterable[tuple[int, str, float, float]],
) -> tuple[list[str], dict[str, int]]:
    options = [format_svg_route_item(item) for item in items]
    return options, {option: int(option.split("|")[0].strip().lstrip("#")) for option in options}


def extract_svg_route_edges_map(mapping_text: object) -> dict[str, object]:
    try:
        mapping = json.loads(str(mapping_text or "{}"))
    except Exception:
        mapping = {}
    if not isinstance(mapping, dict):
        mapping = {}
    edges_map = mapping.get("edges") if isinstance(mapping, dict) else {}
    return edges_map if isinstance(edges_map, dict) else {}


def build_svg_route_coverage(
    edge_columns: Iterable[str],
    edges_map: dict[str, object],
) -> tuple[set[str], list[str], list[dict[str, object]]]:
    mapped_set = set(edges_map.keys()) if isinstance(edges_map, dict) else set()
    unmapped = [edge_name for edge_name in edge_columns if edge_name not in mapped_set]
    rows = [
        {
            "edge": edge_name,
            "mapped": edge_name in mapped_set,
            "segments": len(edges_map.get(edge_name, [])) if isinstance(edges_map.get(edge_name, []), list) else 0,
        }
        for edge_name in edge_columns
    ]
    return mapped_set, unmapped, rows


def suggest_svg_route_filter_text(edge_name: object) -> str:
    target = str(edge_name or "")
    matches = re.findall(r"(ЛП|ЛЗ|ПП|ПЗ)\s*([0-9]+)", target.upper())
    if matches:
        return f"{matches[0][0]}{matches[0][1]}"
    tokens = target.strip().split()
    if tokens:
        return tokens[0][:24]
    return ""
