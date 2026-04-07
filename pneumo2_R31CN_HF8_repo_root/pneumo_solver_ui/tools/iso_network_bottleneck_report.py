# -*- coding: utf-8 -*-
"""Отчёт по «узким местам» ISO 6358 в пневмосети.

Идея:
Для каждого целевого узла (обычно камера цилиндра) оцениваем «пропускную способность» пути
от источников (ресиверы/аккумулятор) как maximin (максимизируем минимальный C_iso на пути).
Это даёт быстрый инженерный ответ:
- какая ветка ограничивает расход (минимальный C_iso на лучшем пути),
- на каком элементе «бутылочное горлышко».

Запуск:
    python tools/iso_network_bottleneck_report.py

Вывод:
- печать в stdout
- файл reports/iso_network_bottlenecks.md
"""

from __future__ import annotations

import json
import math
import heapq
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def widest_paths(
    adj: Dict[int, List[Tuple[int, float, str]]],
    source: int,
) -> Tuple[Dict[int, float], Dict[int, Tuple[int, str]]]:
    """Widest path (maximise bottleneck capacity) in an undirected graph.

    adj[u] -> list of (v, cap, edge_name)
    Returns:
      cap[node] = best bottleneck capacity from source to node
      parent[node] = (prev_node, edge_name)
    """
    cap: Dict[int, float] = {source: float("inf")}
    parent: Dict[int, Tuple[int, str]] = {}

    pq: List[Tuple[float, int]] = [(-cap[source], source)]
    seen = set()

    while pq:
        negc, u = heapq.heappop(pq)
        c = -negc
        if u in seen:
            continue
        seen.add(u)
        for v, ecap, ename in adj.get(u, []):
            if ecap <= 0.0:
                continue
            cand = min(c, ecap)
            if cand > cap.get(v, -1.0):
                cap[v] = cand
                parent[v] = (u, ename)
                heapq.heappush(pq, (-cand, v))

    return cap, parent


def reconstruct_path(parent: Dict[int, Tuple[int, str]], source: int, target: int) -> List[Tuple[int, int, str]]:
    """Return list of (u,v,edge_name) from source to target."""
    if target == source:
        return []
    if target not in parent:
        return []
    path_rev: List[Tuple[int, int, str]] = []
    cur = target
    while cur != source and cur in parent:
        prev, ename = parent[cur]
        path_rev.append((prev, cur, ename))
        cur = prev
    path_rev.reverse()
    return path_rev


def main() -> int:
    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    base = _load_json(root / "default_base.json")

    # Импортируем "каноническую" модель по scheme_fingerprint.json (fallback -> v9 camozzi -> v8 energy)
    import importlib.util, sys

    def _pick_model_path() -> Path:
        fp = root / "scheme_fingerprint.json"
        if fp.exists():
            try:
                meta = _load_json(fp).get("meta", {})
                mf = meta.get("model_file")
                if mf:
                    p = Path(mf)
                    if not p.is_absolute():
                        p = root / p
                    if p.exists():
                        return p
            except Exception:
                pass
        if (root / "model_pneumo_v9_doublewishbone_camozzi.py").exists():
            return root / "model_pneumo_v9_doublewishbone_camozzi.py"
        return root / "model_pneumo_v8_energy_audit_vacuum.py"

    model_path = _pick_model_path()
    spec = importlib.util.spec_from_file_location("model", str(model_path))
    if spec is None or spec.loader is None:
        print("Не удалось загрузить модель:", model_path)
        return 2
    model = importlib.util.module_from_spec(spec)
    sys.modules["model"] = model
    spec.loader.exec_module(model)  # type: ignore

    nodes, node_index, edges, B = model.build_network_full(base)

    # Узлы
    names = [n.name for n in nodes]

    # Источники: ресиверы/аккумулятор/узел после зарядного регулятора (если есть)
    sources = [i for i, n in enumerate(nodes)
               if ("ресивер" in n.name.lower())
               or ("аккум" in n.name.lower())
               or ("узел_после_рег_заряд" in n.name.lower())]
    # Цели: камеры цилиндров
    targets = [i for i, n in enumerate(nodes) if getattr(n, "kind", "") == "chamber"]

    if not sources or not targets:
        print("Не удалось определить sources/targets по именам узлов.")
        return 2

    # Собираем граф (UNDIRECTED) по C_iso
    adj: Dict[int, List[Tuple[int, float, str]]] = {i: [] for i in range(len(nodes))}

    def edge_cap(e) -> float:
        c = getattr(e, "C_iso", None)
        if c is None:
            A = getattr(e, "A", None)
            if A is None:
                return 0.0
            # грубая оценка: C из площади
            try:
                if hasattr(model, "C_from_area_iso"):
                    return float(model.C_from_area_iso(float(A)))
                if hasattr(model, "C_iso_from_area_SMC"):
                    return float(model.C_iso_from_area_SMC(float(A)))
                return 0.0
            except Exception:
                return 0.0
        try:
            return float(c)
        except Exception:
            return 0.0

    edge_by_name = {}
    for e in edges:
        u = int(e.n1)
        v = int(e.n2)
        c = edge_cap(e)
        ename = str(getattr(e, "name", f"edge_{u}_{v}"))
        edge_by_name[ename] = e
        adj[u].append((v, c, ename))
        adj[v].append((u, c, ename))

    # Для каждого target выбираем лучший source (максимальный bottleneck)
    rows = []
    for t in targets:
        best = (-1.0, None, None, [])  # (cap, source_idx, parent_map, path)
        for s in sources:
            cap, parent = widest_paths(adj, s)
            cst = cap.get(t, -1.0)
            if cst > best[0]:
                path = reconstruct_path(parent, s, t)
                best = (cst, s, parent, path)
        best_cap, best_s, _, path = best
        if best_s is None or best_cap <= 0.0 or not path:
            rows.append((names[t], "<нет пути>", 0.0, "", ""))
            continue

        # bottleneck edge in that path
        caps = []
        for u, v, ename in path:
            for vv, cc, nn in adj[u]:
                if vv == v and nn == ename:
                    caps.append((cc, ename))
                    break
        if caps:
            bottleneck_c, bottleneck_e = min(caps, key=lambda x: x[0])
        else:
            bottleneck_c, bottleneck_e = (0.0, "")

        path_str = " -> ".join([names[best_s]] + [names[v] for (_, v, _) in path])
        rows.append((names[t], names[best_s], float(best_cap), str(bottleneck_e), path_str))

    # Формируем markdown
    out_lines = []
    out_lines.append("# ISO 6358 bottleneck report\n")
    out_lines.append("Источники (по имени):\n" + "\n".join([f"- {names[i]}" for i in sources]) + "\n")
    out_lines.append("Цели: камеры цилиндров\n")
    out_lines.append("\n## Лучший maximin-путь до каждой камеры\n")
    out_lines.append("| Камера | Источник | C_bottleneck (макс. из min) | Узкое место (edge) | Путь |\n|---|---|---:|---|---|")

    for cam, src, ccap, bottleneck_e, path_str in rows:
        out_lines.append(f"| {cam} | {src} | {ccap:.3e} | {bottleneck_e} | {path_str} |")

    report_path = root / "reports" / "iso_network_bottlenecks.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print("ISO bottleneck report saved:", report_path)
    print("(Откройте .md файл для таблицы путей и узких мест)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
