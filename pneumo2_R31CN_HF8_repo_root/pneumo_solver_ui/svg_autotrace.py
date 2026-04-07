# -*- coding: utf-8 -*-
"""
svg_autotrace.py

Авто-анализ SVG (пневмосхема) и черновая авто-разметка mapping JSON
для анимации потоков/узлов.

Задача модуля:
  - извлечь линии (<line>) и тексты (<text> + transform matrix)
  - кластеризовать близкие endpoints (tol) -> узлы графа
  - построить сегменты (ребра) и разложить на полилинии (цепочки между узлами степени !=2)
  - сопоставить текстовые метки с ближайшей полилинией
  - собрать mapping JSON v2: edges[name]=[[[x,y],...]], nodes[name]=[x,y]

Важные ограничения:
  - В текущих SVG из Illustrator линии/группы НЕ имеют transform (обычно).
  - Мы не пытаемся "распознавать символы" CAD полноценно (это отдельный этап).
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

import datetime
import math
import heapq
import re
import xml.etree.ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
NS = {"svg": SVG_NS}


@dataclass
class SvgText:
    text: str
    x: float
    y: float
    klass: str = ""


@dataclass
class SvgLine:
    x1: float
    y1: float
    x2: float
    y2: float
    klass: str = ""


def _parse_matrix_translate(transform: str) -> Optional[Tuple[float, float]]:
    """
    SVG text from Illustrator often has transform="matrix(a b c d e f)".
    For position hints we take translation (e,f).
    """
    if not transform:
        return None
    m = re.match(r"matrix\(([^)]+)\)", transform.strip())
    if not m:
        return None
    parts = m.group(1).replace(",", " ").split()
    if len(parts) != 6:
        return None
    try:
        e = float(parts[4])
        f = float(parts[5])
        return (e, f)
    except Exception:
        return None


def parse_svg(svg_text: str) -> Tuple[str, List[SvgLine], List[SvgText]]:
    """
    Возвращает (viewBox, lines, texts)
    """
    # ET can be picky about huge SVG; this is still fine for ~0.5MB.
    root = ET.fromstring(svg_text)

    view_box = root.attrib.get("viewBox", "0 0 1920 1080")

    lines: List[SvgLine] = []
    for el in root.findall(".//svg:line", NS):
        try:
            lines.append(
                SvgLine(
                    x1=float(el.attrib.get("x1", "0")),
                    y1=float(el.attrib.get("y1", "0")),
                    x2=float(el.attrib.get("x2", "0")),
                    y2=float(el.attrib.get("y2", "0")),
                    klass=str(el.attrib.get("class", "")),
                )
            )
        except Exception:
            continue

    texts: List[SvgText] = []
    for el in root.findall(".//svg:text", NS):
        txt = "".join(el.itertext()).strip()
        if not txt:
            continue
        klass = str(el.attrib.get("class", ""))
        pos = _parse_matrix_translate(str(el.attrib.get("transform", "")))
        if pos is None:
            # Some SVG have x/y on <text>; try fallback
            try:
                x = float(el.attrib.get("x", "0"))
                y = float(el.attrib.get("y", "0"))
                pos = (x, y)
            except Exception:
                continue
        texts.append(SvgText(text=txt, x=float(pos[0]), y=float(pos[1]), klass=klass))

    return view_box, lines, texts


# -------------------------
# Graph building
# -------------------------

class DSU:
    def __init__(self, n: int):
        self.p = list(range(n))
        self.r = [0] * n

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        if self.r[ra] < self.r[rb]:
            ra, rb = rb, ra
        self.p[rb] = ra
        if self.r[ra] == self.r[rb]:
            self.r[ra] += 1


def _cluster_points(points: List[Tuple[float, float]], tol: float) -> Tuple[List[Tuple[float, float]], Dict[Tuple[float, float], int]]:
    """
    Кластеризация точек по расстоянию tol (union-find + grid).
    Возвращает:
      - coords: координаты новых узлов (средние по кластеру)
      - point_to_node: исходная точка -> id узла
    """
    if not points:
        return [], {}

    uniq = list(dict.fromkeys(points))  # preserve order, remove duplicates
    n = len(uniq)
    dsu = DSU(n)

    cell = max(1e-6, float(tol))
    grid: Dict[Tuple[int, int], List[int]] = {}

    for i, (x, y) in enumerate(uniq):
        ix, iy = int(x // cell), int(y // cell)
        # check neighbors already inserted
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (ix + dx, iy + dy)
                for j in grid.get(key, []):
                    ox, oy = uniq[j]
                    if (ox - x) * (ox - x) + (oy - y) * (oy - y) <= tol * tol:
                        dsu.union(i, j)
        grid.setdefault((ix, iy), []).append(i)

    rep_to_idx: Dict[int, int] = {}
    clusters: List[List[Tuple[float, float]]] = []
    point_to_node: Dict[Tuple[float, float], int] = {}
    for i, pt in enumerate(uniq):
        rep = dsu.find(i)
        if rep not in rep_to_idx:
            rep_to_idx[rep] = len(clusters)
            clusters.append([])
        cid = rep_to_idx[rep]
        clusters[cid].append(pt)
        point_to_node[pt] = cid

    coords: List[Tuple[float, float]] = []
    for cl in clusters:
        sx = sum(p[0] for p in cl)
        sy = sum(p[1] for p in cl)
        coords.append((sx / len(cl), sy / len(cl)))

    return coords, point_to_node


def build_graph(lines: List[SvgLine], tol_merge: float = 2.1) -> Tuple[List[Tuple[float, float]], List[Tuple[int, int]]]:
    """
    Возвращает (nodes_coords, edges) где edges — список (nodeA, nodeB).
    """
    pts: List[Tuple[float, float]] = []
    for ln in lines:
        pts.append((ln.x1, ln.y1))
        pts.append((ln.x2, ln.y2))

    nodes, pt_to_node = _cluster_points(pts, tol=float(tol_merge))

    edges: List[Tuple[int, int]] = []
    for ln in lines:
        a = pt_to_node.get((ln.x1, ln.y1))
        b = pt_to_node.get((ln.x2, ln.y2))
        if a is None or b is None or a == b:
            continue
        edges.append((a, b))

    return nodes, edges


def _polyline_decompose(nodes: List[Tuple[float, float]], edges: List[Tuple[int, int]]) -> List[List[int]]:
    """
    Разложение графа на полилинии (цепочки) между узлами степени != 2.
    Возвращает список полилиний в виде последовательности node ids.
    """
    from collections import defaultdict

    adj = defaultdict(list)  # node -> list[(nbr, edge_idx)]
    for i, (a, b) in enumerate(edges):
        adj[a].append((b, i))
        adj[b].append((a, i))

    def deg(n: int) -> int:
        return len(adj.get(n, []))

    visited = [False] * len(edges)
    polylines: List[List[int]] = []

    for ei, (a, b) in enumerate(edges):
        if visited[ei]:
            continue

        # choose start
        if deg(a) != 2:
            start, other = a, b
        elif deg(b) != 2:
            start, other = b, a
        else:
            start, other = a, b  # cycle; arbitrary

        poly = [start, other]
        visited[ei] = True

        prev = start
        curr = other
        prev_ei = ei

        while True:
            if deg(curr) != 2:
                break
            # pick next edge != prev_ei
            nxt = None
            for nb, nb_ei in adj[curr]:
                if nb_ei == prev_ei:
                    continue
                nxt = (nb, nb_ei)
                break
            if nxt is None:
                break
            nb, nb_ei = nxt
            if visited[nb_ei]:
                break
            visited[nb_ei] = True
            prev_ei = nb_ei
            curr = nb
            poly.append(curr)

        polylines.append(poly)

    return polylines


def extract_polylines(svg_text: str, tol_merge: float = 2.1) -> Dict[str, Any]:
    """
    Полный анализ SVG -> граф и полилинии.

    Возвращает dict с полями:
      viewBox, nodes, edges, polylines, texts,
      node_degree, degree_counts, junction_nodes, poly_endpoints
    """
    view_box, lines, texts = parse_svg(svg_text)
    nodes, edges = build_graph(lines, tol_merge=tol_merge)
    polylines = _polyline_decompose(nodes, edges)

    # degrees for every node
    deg = _compute_degrees(len(nodes), edges)

    # degree histogram
    from collections import Counter
    deg_counts = Counter(deg)

    # junctions (deg != 2)
    junction_nodes = [
        {"id": int(i), "x": float(nodes[i][0]), "y": float(nodes[i][1]), "deg": int(deg[i])}
        for i in range(len(nodes))
        if deg[i] != 2
    ]

    # poly endpoints + rough length
    poly_endpoints = []
    for pi, poly in enumerate(polylines):
        if not poly:
            continue
        a = int(poly[0])
        b = int(poly[-1])
        length = 0.0
        for u, v in zip(poly, poly[1:]):
            x1, y1 = nodes[u]
            x2, y2 = nodes[v]
            length += math.hypot(x2 - x1, y2 - y1)
        poly_endpoints.append(
            {
                "poly_idx": int(pi),
                "a_id": a,
                "b_id": b,
                "a_deg": int(deg[a]) if 0 <= a < len(deg) else 0,
                "b_deg": int(deg[b]) if 0 <= b < len(deg) else 0,
                "a_xy": [float(nodes[a][0]), float(nodes[a][1])] if 0 <= a < len(nodes) else None,
                "b_xy": [float(nodes[b][0]), float(nodes[b][1])] if 0 <= b < len(nodes) else None,
                "length": float(length),
                "n_points": int(len(poly)),
            }
        )

    return {
        "viewBox": view_box,
        "nodes": nodes,
        "edges": edges,
        "polylines": polylines,
        "texts": [t.__dict__ for t in texts],
        "node_degree": deg,
        "degree_counts": dict(deg_counts),
        "junction_nodes": junction_nodes,
        "poly_endpoints": poly_endpoints,
    }

def analysis_polylines_to_coords(analysis: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
    """Convert extract_polylines() analysis dict into coordinate polylines.

    `extract_polylines()` returns polylines as node-id chains plus a shared `nodes` table.
    UI pages that want to draw/edit SVG geometry must resolve node ids into explicit
    coordinate lists first. The helper is pure and deterministic: it never invents
    points and silently skips malformed node references.
    """
    nodes_raw = list(analysis.get("nodes") or []) if isinstance(analysis, dict) else []
    polylines_raw = list(analysis.get("polylines") or []) if isinstance(analysis, dict) else []

    out: List[List[Tuple[float, float]]] = []
    for poly in polylines_raw:
        coords: List[Tuple[float, float]] = []
        try:
            nids = list(poly)
        except Exception:
            nids = []
        for nid in nids:
            try:
                idx = int(nid)
            except Exception:
                continue
            if idx < 0 or idx >= len(nodes_raw):
                continue
            try:
                node = nodes_raw[idx]
                x = float(node[0])
                y = float(node[1])
            except Exception:
                continue
            coords.append((x, y))
        if len(coords) >= 2:
            out.append(coords)
    return out


# -------------------------
# Matching helpers
# -------------------------

def _pt_seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    vx = x2 - x1
    vy = y2 - y1
    wx = px - x1
    wy = py - y1
    c1 = wx * vx + wy * vy
    if c1 <= 0:
        return math.hypot(px - x1, py - y1)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - x2, py - y2)
    b = c1 / c2
    bx = x1 + b * vx
    by = y1 + b * vy
    return math.hypot(px - bx, py - by)


def _pt_poly_dist(px: float, py: float, coords: List[Tuple[float, float]]) -> float:
    best = 1e18
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        d = _pt_seg_dist(px, py, x1, y1, x2, y2)
        if d < best:
            best = d
    return best


def _compute_degrees(n_nodes: int, edges: List[Tuple[int, int]]) -> List[int]:
    deg = [0] * int(n_nodes)
    for a, b in edges:
        if 0 <= a < n_nodes:
            deg[a] += 1
        if 0 <= b < n_nodes:
            deg[b] += 1
    return deg


def _nearest_node_on_poly(poly_nids: List[int], nodes: List[Tuple[float, float]], px: float, py: float) -> Tuple[int, float]:
    if not poly_nids:
        return -1, 1e18
    best_nid = int(poly_nids[0])
    best_d = 1e18
    for nid in poly_nids:
        x, y = nodes[nid]
        d = math.hypot(px - x, py - y)
        if d < best_d:
            best_d = d
            best_nid = int(nid)
    return best_nid, float(best_d)


def _nearest_point_on_segment(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Tuple[float, float, float, float]:
    """Возвращает ближайшую точку на отрезке (x,y), расстояние и параметр t∈[0..1]."""
    vx = x2 - x1
    vy = y2 - y1
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        d = math.hypot(px - x1, py - y1)
        return float(x1), float(y1), float(d), 0.0
    t = ((px - x1) * vx + (py - y1) * vy) / denom
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    bx = x1 + t * vx
    by = y1 + t * vy
    d = math.hypot(px - bx, py - by)
    return float(bx), float(by), float(d), float(t)


def _nearest_point_on_polyline(
    px: float,
    py: float,
    coords: List[Tuple[float, float]],
) -> Tuple[float, float, float, int]:
    """Ближайшая точка на полилинии (по сегментам). Возвращает (x,y,dist,seg_idx)."""
    best_d = 1e18
    best_x = float(px)
    best_y = float(py)
    best_i = -1
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(coords, coords[1:])):
        bx, by, d, _t = _nearest_point_on_segment(px, py, x1, y1, x2, y2)
        if d < best_d:
            best_d = d
            best_x = bx
            best_y = by
            best_i = i
    return float(best_x), float(best_y), float(best_d), int(best_i)



def _nearest_junction_on_poly(
    poly_nids: List[int],
    nodes: List[Tuple[float, float]],
    deg: List[int],
    px: float,
    py: float,
) -> Optional[Tuple[int, float]]:
    best_nid: Optional[int] = None
    best_d = 1e18
    for nid in poly_nids:
        if 0 <= nid < len(deg) and deg[nid] == 2:
            continue
        x, y = nodes[nid]
        d = math.hypot(px - x, py - y)
        if d < best_d:
            best_d = d
            best_nid = int(nid)
    if best_nid is None:
        return None
    return best_nid, float(best_d)


def _rdp_simplify(points: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
    """Ramer–Douglas–Peucker polyline simplification."""
    if epsilon <= 0 or len(points) < 3:
        return list(points)

    x1, y1 = points[0]
    x2, y2 = points[-1]

    max_d = -1.0
    idx = -1
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = _pt_seg_dist(px, py, x1, y1, x2, y2)
        if d > max_d:
            max_d = d
            idx = i

    if max_d > float(epsilon) and idx >= 0:
        left = _rdp_simplify(points[: idx + 1], epsilon)
        right = _rdp_simplify(points[idx:], epsilon)
        return left[:-1] + right

    return [points[0], points[-1]]



def _norm_name(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[\s\-_]+", " ", s)
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _name_score(a: str, b: str) -> float:
    a1 = _norm_name(a)
    b1 = _norm_name(b)
    if not a1 or not b1:
        return 0.0
    if a1 == b1:
        return 1.0
    sm = SequenceMatcher(None, a1, b1).ratio()
    ta = set(a1.split())
    tb = set(b1.split())
    j = len(ta & tb) / max(1, len(ta | tb))
    return 0.65 * sm + 0.35 * j


def _extract_tokens(name: str) -> List[str]:
    """
    Извлекает "короткие" сигнатуры из имени: ЛП1, ПЗ2, etc.
    """
    if not isinstance(name, str):
        return []
    toks = []
    # Cyrillic corner/line labels like ЛП1, ПЗ2 etc
    for m in re.finditer(r"(ЛП|ЛЗ|ПП|ПЗ)\s*([0-9]+)", name.upper()):
        toks.append(f"{m.group(1)}{m.group(2)}")
    # generic alnum tokens like A12, P3 etc (fallback)
    for m in re.finditer(r"\b([A-ZА-Я]{1,3}\s*[0-9]{1,3})\b", name.upper()):
        tok = re.sub(r"\s+", "", m.group(1))
        if tok not in toks:
            toks.append(tok)
    return toks


def match_labels_to_polylines(
    svg_texts: List[SvgText],
    poly_coords: List[List[Tuple[float, float]]],
    max_dist: float = 80.0,
) -> Dict[str, Dict[str, Any]]:
    """
    Для каждой текстовой метки ищем ближайшую полилинию.

    Если метка встречается несколько раз (например, 'P'/'Q' или повторяющиеся подписи),
    оставляем вариант с минимальным расстоянием до ближайшей полилинии.

    Возвращает dict label -> {poly_idx, dist, x, y}
    """
    out: Dict[str, Dict[str, Any]] = {}
    for t in svg_texts:
        px, py = t.x, t.y
        best_i = None
        best_d = 1e18
        for i, coords in enumerate(poly_coords):
            d = _pt_poly_dist(px, py, coords)
            if d < best_d:
                best_d = d
                best_i = i
        if best_i is None or best_d > float(max_dist):
            continue

        prev = out.get(t.text)
        if prev is None or best_d < float(prev.get("dist", 1e18)):
            out[t.text] = {"poly_idx": int(best_i), "dist": float(best_d), "x": float(px), "y": float(py)}
    return out


def auto_build_mapping_from_svg(
    svg_text: str,
    edge_names: List[str],
    node_names: Optional[List[str]] = None,
    tol_merge: float = 2.1,
    max_label_dist: float = 80.0,
    min_name_score: float = 0.75,
    simplify_epsilon: float = 0.0,
    snap_nodes_to_graph: bool = True,
    prefer_junctions: bool = True,
    node_snap_max_dist: float = 40.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Пытается автоматически построить mapping v2 для заданных edge_names / node_names
    по геометрии линий и позициям текстовых меток.

    Новое (v7.13):
      - nodes (узлы давления) можно "прилипать" к реальным узлам графа (junction/узел линии),
        а не оставлять в координате текста.
      - полилинии можно слегка упростить (RDP) для уменьшения размера mapping (simplify_epsilon).

    Возвращает:
      mapping, report
    """
    view_box, lines, texts = parse_svg(svg_text)
    nodes, edges = build_graph(lines, tol_merge=tol_merge)
    polylines_nids = _polyline_decompose(nodes, edges)
    poly_coords_full = [[nodes[nid] for nid in poly] for poly in polylines_nids]

    # degrees for snapping heuristics
    deg = _compute_degrees(len(nodes), edges)

    # Build label->poly match
    label_match = match_labels_to_polylines(texts, poly_coords_full, max_dist=max_label_dist)

    # Helper: label candidates list
    labels = list(label_match.keys())

    mapping: Dict[str, Any] = {
        "version": 2,
        "viewBox": view_box,
        "edges": {},
        "nodes": {},
        "meta": {
            "generated_by": "svg_autotrace.py",
            "generated_utc": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
            "tol_merge": float(tol_merge),
            "max_label_dist": float(max_label_dist),
            "min_name_score": float(min_name_score),
            "simplify_epsilon": float(simplify_epsilon),
            "snap_nodes_to_graph": bool(snap_nodes_to_graph),
            "prefer_junctions": bool(prefer_junctions),
            "node_snap_max_dist": float(node_snap_max_dist),
        },
        "edges_meta": {},
        "nodes_meta": {},
    }
    report: Dict[str, Any] = {"edges": [], "nodes": [], "unmatched_edges": [], "unmatched_nodes": []}
    node_names = node_names or []

    # Map edges: prefer token match, else fuzzy to labels
    for en in edge_names:
        target_labels = _extract_tokens(en)
        chosen_label = None
        chosen_score = 0.0

        for tok in target_labels:
            if tok in label_match:
                chosen_label = tok
                chosen_score = 1.0
                break

        if chosen_label is None:
            # fuzzy against labels
            best = None
            best_s = 0.0
            for lbl in labels:
                s = _name_score(en, lbl)
                if s > best_s:
                    best_s = s
                    best = lbl
            if best is not None and best_s >= float(min_name_score):
                chosen_label = best
                chosen_score = best_s

        if chosen_label is None:
            mapping["edges"][en] = []
            report["unmatched_edges"].append(en)
            continue

        poly_idx = int(label_match[chosen_label]["poly_idx"])
        coords = poly_coords_full[poly_idx]
        if float(simplify_epsilon) > 0.0 and len(coords) > 2:
            coords = _rdp_simplify(coords, float(simplify_epsilon))

        mapping["edges"][en] = [[[float(x), float(y)] for (x, y) in coords]]
        mapping["edges_meta"][en] = {
            "label": chosen_label,
            "score": float(chosen_score),
            "dist_label_poly": float(label_match[chosen_label]["dist"]),
            "poly_idx": int(poly_idx),
            "n_points": int(len(coords)),
        }
        report["edges"].append(
            {
                "edge": en,
                "label": chosen_label,
                "score": float(chosen_score),
                "dist": float(label_match[chosen_label]["dist"]),
                "poly_idx": int(poly_idx),
                "n_points": int(len(coords)),
            }
        )

    # Map nodes: prefer token match, else fuzzy to labels
    # New: snap to nearest graph node / junction on the matched polyline.
    for nn in node_names:
        target_labels = _extract_tokens(nn)
        chosen_label = None
        chosen_score = 0.0

        for tok in target_labels:
            if tok in label_match:
                chosen_label = tok
                chosen_score = 1.0
                break

        if chosen_label is None:
            best = None
            best_s = 0.0
            for lbl in labels:
                s = _name_score(nn, lbl)
                if s > best_s:
                    best_s = s
                    best = lbl
            if best is not None and best_s >= float(min_name_score):
                chosen_label = best
                chosen_score = best_s

        if chosen_label is None:
            mapping["nodes"][nn] = None
            mapping["nodes_meta"][nn] = {"ok": False}
            report["unmatched_nodes"].append(nn)
            continue

        poly_idx = int(label_match[chosen_label]["poly_idx"])
        px = float(label_match[chosen_label]["x"])
        py = float(label_match[chosen_label]["y"])
        dist_label_poly = float(label_match[chosen_label]["dist"])

        snap_mode = "label"
        snap_nid: Optional[int] = None
        dist_label_node: Optional[float] = None
        snap_xy: Optional[Tuple[float, float]] = None
        near_nid: Optional[int] = None

        poly_nids = polylines_nids[poly_idx] if 0 <= poly_idx < len(polylines_nids) else []

        if snap_nodes_to_graph and poly_nids:
            # 1) Prefer junction nodes (deg != 2) close to label
            if prefer_junctions:
                res = _nearest_junction_on_poly(poly_nids, nodes, deg, px, py)
                if res is not None:
                    nid_j, d_j = res
                    if d_j <= float(node_snap_max_dist):
                        snap_nid = int(nid_j)
                        dist_label_node = float(d_j)
                        snap_mode = "junction"
                        if 0 <= snap_nid < len(nodes):
                            snap_xy = (float(nodes[snap_nid][0]), float(nodes[snap_nid][1]))
                        near_nid = snap_nid

            # 2) Fallback: nearest point on that polyline (projection to segment)
            if snap_nid is None:
                coords_poly = poly_coords_full[poly_idx] if (0 <= poly_idx < len(poly_coords_full)) else []
                if len(coords_poly) >= 2:
                    bx, by, d, seg_i = _nearest_point_on_polyline(px, py, coords_poly)
                    snap_xy = (float(bx), float(by))
                    dist_label_node = float(d)
                    snap_mode = "poly_point"
                    # nearest endpoint node id (для справки/связности)
                    if 0 <= seg_i < len(poly_nids) - 1:
                        a = int(poly_nids[seg_i])
                        b = int(poly_nids[seg_i + 1])
                        ax, ay = nodes[a]
                        bx2, by2 = nodes[b]
                        da = math.hypot(bx - ax, by - ay)
                        db = math.hypot(bx - bx2, by - by2)
                        near_nid = a if da <= db else b

        if snap_xy is not None:
            mapping["nodes"][nn] = [float(snap_xy[0]), float(snap_xy[1])]
        else:
            mapping["nodes"][nn] = [float(px), float(py)]

        mapping["nodes_meta"][nn] = {
            "ok": True,
            "label": chosen_label,
            "score": float(chosen_score),
            "poly_idx": int(poly_idx),
            "dist_label_poly": float(dist_label_poly),
            "snap_mode": snap_mode,
            "snap_node_id": int(snap_nid) if snap_nid is not None else None,
            "snap_node_deg": int(deg[snap_nid]) if (snap_nid is not None and 0 <= snap_nid < len(deg)) else None,
            "near_node_id": int(near_nid) if near_nid is not None else None,
            "near_node_deg": int(deg[near_nid]) if (near_nid is not None and 0 <= near_nid < len(deg)) else None,
            "snap_xy": [float(snap_xy[0]), float(snap_xy[1])] if snap_xy is not None else None,
            "dist_label_node": float(dist_label_node) if dist_label_node is not None else None,
        }

        report["nodes"].append(
            {
                "node": nn,
                "label": chosen_label,
                "score": float(chosen_score),
                "poly_idx": int(poly_idx),
                "dist_label_poly": float(dist_label_poly),
                "snap_mode": snap_mode,
                "snap_node_id": int(snap_nid) if snap_nid is not None else None,
                "snap_node_deg": int(deg[snap_nid]) if (snap_nid is not None and 0 <= snap_nid < len(deg)) else None,
                "near_node_id": int(near_nid) if near_nid is not None else None,
                "near_node_deg": int(deg[near_nid]) if (near_nid is not None and 0 <= near_nid < len(deg)) else None,
                "snap_xy": [float(snap_xy[0]), float(snap_xy[1])] if snap_xy is not None else None,
                "dist_label_node": float(dist_label_node) if dist_label_node is not None else None,
            }
        )

    # Add summary
    report["summary"] = {
        "polylines": len(poly_coords_full),
        "nodes": len(nodes),
        "edges": len(edges),
        "labels": len(labels),
        "tol_merge": float(tol_merge),
        "max_label_dist": float(max_label_dist),
        "min_name_score": float(min_name_score),
        "simplify_epsilon": float(simplify_epsilon),
        "snap_nodes_to_graph": bool(snap_nodes_to_graph),
        "prefer_junctions": bool(prefer_junctions),
        "node_snap_max_dist": float(node_snap_max_dist),
    }
    return mapping, report

def detect_component_bboxes(
    svg_text: str,
    keywords: Optional[List[str]] = None,
    radius: float = 120.0,
) -> List[Dict[str, Any]]:
    """
    Очень грубая детекция "компонентов" по текстовым меткам:
    вокруг метки собираем линии в радиусе и строим bbox.

    Возвращает список:
      {label, x, y, kind, bbox=[x0,y0,x1,y1], lines_count}
    """
    view_box, lines, texts = parse_svg(svg_text)
    keywords = keywords or ["Ресивер", "Аккумулятор", "Рег.", "Регулятор", "Клапан", "Обрат", "Дросс"]
    out: List[Dict[str, Any]] = []

    # Precompute lines bboxes for quick inclusion
    line_bbs: List[Tuple[float, float, float, float]] = []
    for ln in lines:
        x0 = min(ln.x1, ln.x2)
        x1 = max(ln.x1, ln.x2)
        y0 = min(ln.y1, ln.y2)
        y1 = max(ln.y1, ln.y2)
        line_bbs.append((x0, y0, x1, y1))

    r2 = float(radius) * float(radius)

    for t in texts:
        if not any(k in t.text for k in keywords):
            continue
        cx, cy = t.x, t.y

        xs: List[float] = []
        ys: List[float] = []
        cnt = 0
        for ln, bb in zip(lines, line_bbs):
            # quick bbox distance
            x0, y0, x1, y1 = bb
            dx = 0.0 if (x0 <= cx <= x1) else min(abs(cx - x0), abs(cx - x1))
            dy = 0.0 if (y0 <= cy <= y1) else min(abs(cy - y0), abs(cy - y1))
            if dx * dx + dy * dy > r2:
                continue
            # accept line: include its endpoints
            xs.extend([ln.x1, ln.x2])
            ys.extend([ln.y1, ln.y2])
            cnt += 1

        if cnt <= 0:
            continue

        bbox = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
        kind = "component"
        if "Ресивер" in t.text:
            kind = "receiver"
        elif "Аккумулятор" in t.text:
            kind = "accumulator"
        elif "Рег" in t.text:
            kind = "regulator"
        out.append(
            {
                "label": t.text,
                "x": float(cx),
                "y": float(cy),
                "kind": kind,
                "bbox": bbox,
                "lines_count": int(cnt),
            }
        )

    return out
# ----------------------------------------------------------------------
# Connectivity / pathfinding helpers (v7.15)
# ----------------------------------------------------------------------

def _project_point_to_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> Tuple[float, float, float, float]:
    """
    Проекция точки P на отрезок AB.

    Возвращает:
      (qx, qy, t, dist2) где Q = A + t*(B-A), t ∈ [0..1]
    """
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    vv = vx * vx + vy * vy
    if vv <= 1e-18:
        # A==B
        dx = px - ax
        dy = py - ay
        return ax, ay, 0.0, dx * dx + dy * dy
    t = (wx * vx + wy * vy) / vv
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    qx = ax + t * vx
    qy = ay + t * vy
    dx = px - qx
    dy = py - qy
    return qx, qy, t, dx * dx + dy * dy


def _nearest_edge_projection(
    nodes: List[Tuple[float, float]],
    edges: List[Tuple[int, int]],
    px: float,
    py: float,
) -> Optional[Dict[str, Any]]:
    """
    Находит ближайшее ребро (отрезок) графа к точке (px,py) и проекцию на него.
    Возвращает dict или None если edges пуст.
    """
    if not edges:
        return None
    best = None
    best_d2 = 1e100
    for ei, (a, b) in enumerate(edges):
        if not (0 <= a < len(nodes) and 0 <= b < len(nodes)):
            continue
        ax, ay = nodes[a]
        bx, by = nodes[b]
        qx, qy, t, d2 = _project_point_to_segment(px, py, ax, ay, bx, by)
        if d2 < best_d2:
            best_d2 = d2
            best = {"edge_idx": int(ei), "a": int(a), "b": int(b), "qx": float(qx), "qy": float(qy), "t": float(t), "dist2": float(d2)}
    return best


def _split_edge_by_point(
    nodes: List[Tuple[float, float]],
    edges: List[Tuple[int, int]],
    px: float,
    py: float,
    snap_eps_px: float = 0.25,
) -> Tuple[int, Dict[str, Any]]:
    """
    Врезает точку в ближайшее ребро графа: удаляет ребро (a,b), добавляет (a,new),(new,b).
    Если проекция очень близко к концу — “снэпает” к существующему узлу и не создаёт новый.

    Возвращает (node_id, info)
    """
    hit = _nearest_edge_projection(nodes, edges, px, py)
    if hit is None:
        raise ValueError("Graph has no edges (cannot attach point).")

    ei = int(hit["edge_idx"])
    a = int(hit["a"])
    b = int(hit["b"])
    qx = float(hit["qx"])
    qy = float(hit["qy"])
    t = float(hit["t"])
    dist_edge = math.sqrt(float(hit["dist2"]))

    ax, ay = nodes[a]
    bx, by = nodes[b]

    # if very close to endpoints -> snap
    da = math.hypot(qx - ax, qy - ay)
    db = math.hypot(qx - bx, qy - by)
    if da <= snap_eps_px:
        return a, {"mode": "snap_endpoint", "which": "a", "edge_idx": ei, "a": a, "b": b, "qx": qx, "qy": qy, "t": t, "dist_to_edge": dist_edge}
    if db <= snap_eps_px:
        return b, {"mode": "snap_endpoint", "which": "b", "edge_idx": ei, "a": a, "b": b, "qx": qx, "qy": qy, "t": t, "dist_to_edge": dist_edge}

    # create new node
    nid = len(nodes)
    nodes.append((qx, qy))

    # replace the edge by two edges
    # keep graph undirected
    try:
        edges.pop(ei)
    except Exception:
        # fallback: leave original
        pass
    edges.append((a, nid))
    edges.append((nid, b))

    return nid, {"mode": "split_edge", "edge_idx": ei, "a": a, "b": b, "new": nid, "qx": qx, "qy": qy, "t": t, "dist_to_edge": dist_edge}


def _build_adj_weighted(nodes: List[Tuple[float, float]], edges: List[Tuple[int, int]]) -> List[List[Tuple[int, float]]]:
    adj: List[List[Tuple[int, float]]] = [[] for _ in range(len(nodes))]
    for (a, b) in edges:
        if not (0 <= a < len(nodes) and 0 <= b < len(nodes) and a != b):
            continue
        ax, ay = nodes[a]
        bx, by = nodes[b]
        w = math.hypot(ax - bx, ay - by)
        adj[a].append((b, w))
        adj[b].append((a, w))
    return adj


def _dijkstra_path(adj: List[List[Tuple[int, float]]], start: int, goal: int) -> Tuple[List[int], float]:
    """
    Dijkstra: возвращает (path_node_ids, total_len). Если пути нет — ([], inf).
    """
    n = len(adj)
    if not (0 <= start < n and 0 <= goal < n):
        return [], float("inf")
    dist = [float("inf")] * n
    prev = [-1] * n
    dist[start] = 0.0
    heap: List[Tuple[float, int]] = [(0.0, start)]

    while heap:
        d, u = heapq.heappop(heap)
        if d != dist[u]:
            continue
        if u == goal:
            break
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if not math.isfinite(dist[goal]):
        return [], float("inf")

    # reconstruct
    path = []
    cur = goal
    while cur != -1:
        path.append(cur)
        if cur == start:
            break
        cur = prev[cur]
    path.reverse()
    if not path or path[0] != start:
        return [], float("inf")
    return path, float(dist[goal])


def shortest_path_between_points(
    nodes_coords: List[List[float]],
    edges_ab: List[List[int]],
    p_start: Tuple[float, float],
    p_end: Tuple[float, float],
    *,
    snap_eps_px: float = 0.25,
    simplify_epsilon: float = 0.0,
) -> Dict[str, Any]:
    """
    Находит кратчайший путь по графу труб (line endpoints) между двумя точками (в координатах SVG).

    Узлы графа: cluster endpoints линий (<line>).
    Рёбра графа: сегменты между endpoints.

    Чтобы старт/финиш могли быть “внутри” сегмента, мы “врезаем” две точки в ближайшие рёбра (split_edge),
    после чего запускаем Dijkstra.

    Возвращает dict (удобно сохранять как json).
    """
    # normalize
    nodes: List[Tuple[float, float]] = []
    for xy in nodes_coords:
        try:
            nodes.append((float(xy[0]), float(xy[1])))
        except Exception:
            continue
    edges: List[Tuple[int, int]] = []
    for ab in edges_ab:
        try:
            edges.append((int(ab[0]), int(ab[1])))
        except Exception:
            continue

    if not nodes or not edges:
        raise ValueError("Empty graph (nodes/edges). Сделайте анализ SVG сначала и проверьте, что в SVG есть <line>.")

    sx, sy = float(p_start[0]), float(p_start[1])
    tx, ty = float(p_end[0]), float(p_end[1])

    # split for start and end
    s_id, s_info = _split_edge_by_point(nodes, edges, sx, sy, snap_eps_px=float(snap_eps_px))
    t_id, t_info = _split_edge_by_point(nodes, edges, tx, ty, snap_eps_px=float(snap_eps_px))

    # run Dijkstra
    adj = _build_adj_weighted(nodes, edges)
    path_nids, total_len = _dijkstra_path(adj, s_id, t_id)
    if not path_nids:
        raise ValueError("Path not found (graph disconnected or wrong attach).")

    path_xy: List[Tuple[float, float]] = [(float(nodes[nid][0]), float(nodes[nid][1])) for nid in path_nids]
    if simplify_epsilon and simplify_epsilon > 0:
        try:
            path_xy = _rdp_simplify(path_xy, float(simplify_epsilon))
        except Exception:
            pass

    return {
        "ok": True,
        "length": float(total_len),
        "node_count": int(len(path_nids)),
        "path_nodes": [int(n) for n in path_nids],
        "path_xy": [[float(x), float(y)] for (x, y) in path_xy],
        "attach_start": s_info,
        "attach_end": t_info,
        "params": {"snap_eps_px": float(snap_eps_px), "simplify_epsilon": float(simplify_epsilon)},
    }


# ----------------------------------------------------------------------
# Route quality / validation helpers (used by UI AUTO-mapping review)
# ----------------------------------------------------------------------

def _polyline_length(path_xy: List[List[float]]) -> float:
    try:
        pts = [(float(p[0]), float(p[1])) for p in path_xy if isinstance(p, (list, tuple)) and len(p) >= 2]
    except Exception:
        pts = []
    if len(pts) < 2:
        return 0.0
    s = 0.0
    x0, y0 = pts[0]
    for (x1, y1) in pts[1:]:
        s += math.hypot(x1 - x0, y1 - y0)
        x0, y0 = x1, y1
    return float(s)


def _count_turns(path_xy: List[List[float]], min_turn_deg: float = 45.0) -> int:
    """
    Считает количество "резких" поворотов в полилинии.
    Внутренняя эвристика: угол между соседними сегментами > min_turn_deg.
    """
    try:
        pts = [(float(p[0]), float(p[1])) for p in path_xy if isinstance(p, (list, tuple)) and len(p) >= 2]
    except Exception:
        pts = []
    if len(pts) < 3:
        return 0
    thr = math.radians(float(min_turn_deg))
    cnt = 0
    for i in range(1, len(pts) - 1):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        v1x, v1y = (x1 - x0), (y1 - y0)
        v2x, v2y = (x2 - x1), (y2 - y1)
        n1 = math.hypot(v1x, v1y)
        n2 = math.hypot(v2x, v2y)
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        v1x /= n1; v1y /= n1
        v2x /= n2; v2y /= n2
        dot = max(-1.0, min(1.0, v1x * v2x + v1y * v2y))
        ang = math.acos(dot)  # 0..pi
        if ang >= thr:
            cnt += 1
    return int(cnt)


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax: float, ay: float, bx: float, by: float, px: float, py: float, eps: float = 1e-9) -> bool:
    return (min(ax, bx) - eps <= px <= max(ax, bx) + eps) and (min(ay, by) - eps <= py <= max(ay, by) + eps)


def _segments_intersect(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
    d: Tuple[float, float],
    eps: float = 1e-9,
) -> bool:
    """
    Проверка пересечения отрезков AB и CD (включая касание).
    """
    ax, ay = a; bx, by = b; cx, cy = c; dx, dy = d
    o1 = _orient(ax, ay, bx, by, cx, cy)
    o2 = _orient(ax, ay, bx, by, dx, dy)
    o3 = _orient(cx, cy, dx, dy, ax, ay)
    o4 = _orient(cx, cy, dx, dy, bx, by)

    # general case
    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (o3 > eps and o4 < -eps or o3 < -eps and o4 > eps):
        return True

    # collinear / touching
    if abs(o1) <= eps and _on_segment(ax, ay, bx, by, cx, cy, eps):
        return True
    if abs(o2) <= eps and _on_segment(ax, ay, bx, by, dx, dy, eps):
        return True
    if abs(o3) <= eps and _on_segment(cx, cy, dx, dy, ax, ay, eps):
        return True
    if abs(o4) <= eps and _on_segment(cx, cy, dx, dy, bx, by, eps):
        return True
    return False


def _count_self_intersections(path_xy: List[List[float]], max_segments: int = 800) -> int:
    """
    Считает самопересечения полилинии (очень грубо, O(n^2)).
    Для больших маршрутов отключается.
    """
    try:
        pts = [(float(p[0]), float(p[1])) for p in path_xy if isinstance(p, (list, tuple)) and len(p) >= 2]
    except Exception:
        pts = []
    if len(pts) < 4:
        return 0
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if len(segs) > int(max_segments):
        return -1  # too expensive
    cnt = 0
    for i in range(len(segs)):
        a, b = segs[i]
        for j in range(i + 2, len(segs)):
            # skip adjacent segments sharing endpoints (i,i+1) and also (i-1,i) already excluded by j>=i+2
            if j == i:
                continue
            c, d = segs[j]
            # skip if they share an endpoint (common in polylines)
            if a == c or a == d or b == c or b == d:
                continue
            if _segments_intersect(a, b, c, d):
                cnt += 1
                # early stop: one intersection is already suspicious
                if cnt >= 3:
                    return int(cnt)
    return int(cnt)


def evaluate_route_quality(
    path_xy: List[List[float]],
    attach_start: Optional[Dict[str, Any]] = None,
    attach_end: Optional[Dict[str, Any]] = None,
    *,
    min_turn_deg: float = 45.0,
    max_detour: float = 8.0,
    max_attach_dist: float = 35.0,
    max_points: int = 2000,
    max_segments_for_intersections: int = 800,
) -> Dict[str, Any]:
    """
    Оценка качества маршрута (beta).

    Возвращает dict:
      - length_px
      - straight_px
      - detour_ratio
      - points
      - turns
      - self_intersections (>=0) или -1 если не считали
      - attach_start_dist / attach_end_dist (label->edge dist)
      - grade: PASS / WARN / FAIL
      - reasons: список причин/предупреждений
      - params: использованные пороги
    """
    reasons: List[str] = []
    try:
        pts = [(float(p[0]), float(p[1])) for p in path_xy if isinstance(p, (list, tuple)) and len(p) >= 2]
    except Exception:
        pts = []
    npts = len(pts)
    length_px = _polyline_length(path_xy)
    if npts >= 2:
        straight = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    else:
        straight = 0.0
    detour = float(length_px / max(1e-9, straight)) if straight > 1e-9 else float("inf")

    turns = _count_turns(path_xy, min_turn_deg=float(min_turn_deg))
    inter = _count_self_intersections(path_xy, max_segments=int(max_segments_for_intersections))

    a_s = None
    a_e = None
    try:
        if isinstance(attach_start, dict):
            a_s = float(attach_start.get("dist_to_edge", None)) if attach_start.get("dist_to_edge", None) is not None else None
    except Exception:
        a_s = None
    try:
        if isinstance(attach_end, dict):
            a_e = float(attach_end.get("dist_to_edge", None)) if attach_end.get("dist_to_edge", None) is not None else None
    except Exception:
        a_e = None

    # Grade heuristics
    grade = "PASS"
    if npts < 2:
        grade = "FAIL"
        reasons.append("Путь пустой/слишком короткий.")
    if npts > int(max_points):
        grade = "WARN" if grade == "PASS" else grade
        reasons.append(f"Очень много точек ({npts}); проверьте simplify.")
    if math.isfinite(detour) and detour > float(max_detour):
        grade = "WARN" if grade == "PASS" else grade
        reasons.append(f"Большая 'извилистость' (detour≈{detour:.1f}). Возможно, выбраны неправильные метки.")
    if inter > 0:
        grade = "FAIL"
        reasons.append(f"Самопересечения маршрута: {inter}.")
    if inter == -1:
        grade = "WARN" if grade == "PASS" else grade
        reasons.append("Самопересечения не считались (слишком много сегментов).")
    if a_s is not None and a_s > float(max_attach_dist):
        grade = "WARN" if grade == "PASS" else grade
        reasons.append(f"START метка далеко от трубки (dist≈{a_s:.1f}px).")
    if a_e is not None and a_e > float(max_attach_dist):
        grade = "WARN" if grade == "PASS" else grade
        reasons.append(f"END метка далеко от трубки (dist≈{a_e:.1f}px).")

    return {
        "length_px": float(length_px),
        "straight_px": float(straight),
        "detour_ratio": float(detour) if math.isfinite(detour) else None,
        "points": int(npts),
        "turns": int(turns),
        "self_intersections": int(inter),
        "attach_start_dist": float(a_s) if a_s is not None else None,
        "attach_end_dist": float(a_e) if a_e is not None else None,
        "grade": str(grade),
        "reasons": [str(r) for r in reasons],
        "params": {
            "min_turn_deg": float(min_turn_deg),
            "max_detour": float(max_detour),
            "max_attach_dist": float(max_attach_dist),
            "max_points": int(max_points),
            "max_segments_for_intersections": int(max_segments_for_intersections),
        },
    }

