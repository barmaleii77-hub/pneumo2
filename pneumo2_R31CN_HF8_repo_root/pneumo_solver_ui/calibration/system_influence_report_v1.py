# -*- coding: utf-8 -*-
"""system_influence_report_v1.py

Отчёт "System Influence" — влияние параметров на систему в целом
(пневматика + кинематика/геометрия), чтобы:
- понимать, какие параметры реально "рулят" системой;
- строить план стадий (staging) и отбрасывать маловлияющие параметры;
- иметь физически осмысленный приоритет до запуска тяжёлой оптимизации.

Ключевая идея:
1) Пневматика: строим граф сети (build_network_full) и считаем
   эталонную пропускную способность ребер (mdot_ref) при заданных p_up/p_dn.
   Для каждой камеры ищем "widest path" от источников (ресиверы/аккумулятор)
   к камере. Bottleneck ребро = минимальная пропускная способность на пути.
   Основная метрика сети — min_bottleneck_mdot по всем камерам.

2) Кинематика/геометрия: считаем быстрые прокси метрики (устойчивость/жёсткости),
   зависящие от базы/колеи/высоты ЦМ/массы/пружины/шины/геометрии цилиндров:
   - phi_crit, theta_crit (геометрические критические углы)
   - Kphi, Ktheta (прокси жёсткость по крену/тангажу)
   - f_roll, f_pitch (прокси собственные частоты)

3) Для каждого параметра оцениваем безразмерную эластичность
   E = d ln(metric) / d ln(param) через малое относительное возмущение.

Выход (в run_dir):
- SYSTEM_INFLUENCE.md
- system_influence.json
- system_influence_params.csv
- system_influence_edges.csv
- system_influence_paths.csv

Запуск:
  python calibration/system_influence_report_v1.py --run_dir calibration_runs/RUN_..._autopilot_v19

"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
# Ensure project package is importable even when this script is launched directly
_THIS = Path(__file__).resolve()
if _THIS.parent.name == "calibration":
    _PNEUMO_ROOT = _THIS.parent.parent  # .../pneumo_solver_ui
else:
    _PNEUMO_ROOT = _THIS.parent  # .../pneumo_solver_ui
_PROJECT_ROOT = _PNEUMO_ROOT.parent  # .../project root
for _p in (str(_PROJECT_ROOT), str(_PNEUMO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pneumo_solver_ui.module_loading import load_python_module_from_path


# --------------------------
# IO helpers
# --------------------------

def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def _save_csv(df: pd.DataFrame, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, encoding="utf-8-sig")


def _fmt(x: Any, nd: int = 6) -> str:
    try:
        xf = float(x)
    except Exception:
        return str(x)
    if not math.isfinite(xf):
        return str(x)
    ax = abs(xf)
    if ax != 0 and (ax < 1e-4 or ax > 1e6):
        return f"{xf:.{nd}e}"
    return f"{xf:.{nd}f}"


def load_py_module(path: Path, module_name: str):
    return load_python_module_from_path(path, module_name)


# --------------------------
# Widest path (maximin) on undirected graph
# --------------------------

@dataclass
class EdgeInfo:
    idx: int
    name: str
    n1: int
    n2: int
    kind: str
    group: str
    C_iso: Optional[float]
    b_iso: Optional[float]
    m_iso: Optional[float]
    A: float
    Cd: float
    dp_crack: float
    mdot_ref: float


def widest_path(adj: Dict[int, List[Tuple[int, int]]], cap: Dict[int, float], src: int, dst: int) -> Tuple[float, List[int]]:
    """Максимизирует min(cap(edge)) на пути src->dst.

    Возвращает:
    - bottleneck (float)
    - путь как список edge_idx (в порядке прохождения)
    """
    if src == dst:
        return float("inf"), []

    best: Dict[int, float] = {src: float("inf")}
    parent: Dict[int, Tuple[int, int]] = {}
    # max-heap by best capacity
    heap: List[Tuple[float, int]] = [(-best[src], src)]

    while heap:
        negc, u = heap.pop(0)
        c_u = -negc
        # Early exit: if this is not current best
        if c_u < best.get(u, 0.0) - 1e-12:
            continue
        if u == dst:
            break
        for v, eidx in adj.get(u, []):
            w = min(best[u], cap.get(eidx, 0.0))
            if w > best.get(v, 0.0) + 1e-15:
                best[v] = w
                parent[v] = (u, eidx)
                # push and keep heap sorted (graph small; avoid heapq for clarity)
                heap.append((-w, v))
        heap.sort(key=lambda x: x[0])

    if dst not in best:
        return 0.0, []

    # reconstruct edges
    edges: List[int] = []
    cur = dst
    while cur != src:
        pu, eidx = parent[cur]
        edges.append(eidx)
        cur = pu
    edges.reverse()
    return best[dst], edges


# --------------------------
# Metrics (pneumo + mech)
# --------------------------


def _safe_float(x: Any) -> Optional[float]:
    try:
        xf = float(x)
        if not math.isfinite(xf):
            return None
        return xf
    except Exception:
        return None


def _spring_slope(params: Dict[str, Any], delta_ref_m: float = 0.05) -> float:
    """Локальная жёсткость табличной пружины около delta_ref.

    Таблица хранится в params как:
      пружина_таблица_ход_мм: [..]
      пружина_таблица_сила_Н: [..]

    Если таблицы нет — возвращаем 0.
    """
    xs = params.get("пружина_таблица_ход_мм")
    ys = params.get("пружина_таблица_сила_Н")
    if not isinstance(xs, list) or not isinstance(ys, list) or len(xs) < 2 or len(xs) != len(ys):
        return 0.0

    x = np.array(xs, dtype=float) * 1e-3
    y = np.array(ys, dtype=float)

    # clamp ref inside table
    delta = float(delta_ref_m)
    delta = max(float(np.min(x)), min(float(np.max(x)), delta))

    # simple numeric derivative via central diff on interpolant
    def interp(xx: float) -> float:
        return float(np.interp(xx, x, y))

    h = max(1e-4, 0.02 * (float(np.max(x)) - float(np.min(x))))
    x1 = max(float(np.min(x)), delta - h)
    x2 = min(float(np.max(x)), delta + h)
    if abs(x2 - x1) < 1e-9:
        return 0.0
    return (interp(x2) - interp(x1)) / (x2 - x1)


def compute_mech_proxies(params: Dict[str, Any]) -> Dict[str, float]:
    """Быстрые прокси метрики кинематики/геометрии.

    Важно: это не замена полной динамики. Это "быстрые физические индикаторы",
    чтобы ранжировать параметры и понимать направления влияния.
    """
    # defaults aligned with model_pneumo_v8_energy_audit_vacuum.py
    g = 9.81
    wheelbase = float(params.get("база", 2.3))
    track = float(params.get("колея", 1.2))
    h_cg = float(params.get("высота_центра_масс", 0.6))

    # frame dimensions if absent
    W = float(params.get("ширина_рамы", 0.30 * track))
    H = float(params.get("высота_рамы", 2.0 * W))
    L = float(params.get("длина_рамы", 6.0 * W))

    m_body = float(params.get("масса_рамы", 600.0))

    I_roll = (1.0 / 12.0) * m_body * (W * W + H * H)
    I_pitch = (1.0 / 12.0) * m_body * (L * L + H * H)

    # geometric critical angles (same as simulate)
    phi_crit = math.atan2((track / 2.0), max(h_cg, 1e-6))
    theta_crit = math.atan2((wheelbase / 2.0), max(h_cg, 1e-6))

    # tire + spring stiffness (proxy)
    k_tire = float(params.get("жёсткость_шины", 200000.0))
    # table spring slope * scale
    k_spring = _spring_slope(params) * float(params.get("пружина_масштаб", 1.0))

    # pneumatic stiffness proxy (gas spring)
    # use same mid-stroke for all cylinders
    P_ATM = float(getattr(params, "P_ATM", 101325.0))
    # but params is dict, so take from model if injected later

    # choose typical pressure
    P_ref = _safe_float(params.get("давление_Pmid_сброс"))
    if P_ref is None:
        P_ref = 101325.0 + 3e5
    # ensure absolute-ish
    if P_ref < 5e4:
        P_ref = 101325.0 + max(P_ref, 0.0)

    gamma = float(params.get("показатель_адиабаты", 1.4))

    # geometry of cylinders (fallback to model defaults)
    d_p1 = float(params.get("диаметр_поршня_Ц1", 0.12))
    d_r1 = float(params.get("диаметр_штока_Ц1", 0.04))
    d_p2 = float(params.get("диаметр_поршня_Ц2", 0.10))
    d_r2 = float(params.get("диаметр_штока_Ц2", 0.04))

    A1_cap = math.pi * (d_p1 * 0.5) ** 2
    A1_rod = max(0.0, A1_cap - math.pi * (d_r1 * 0.5) ** 2)
    A2_cap = math.pi * (d_p2 * 0.5) ** 2
    A2_rod = max(0.0, A2_cap - math.pi * (d_r2 * 0.5) ** 2)

    L_stroke = float(params.get("ход_штока", 0.10))
    s0 = 0.5 * L_stroke

    V_dead = float(params.get("мёртвый_объём_камеры", 3e-4))

    def gas_k(A_cap: float, A_rod: float) -> float:
        # volumes at mid-stroke
        V_cap = max(1e-9, V_dead + A_cap * s0)
        V_rod = max(1e-9, V_dead + A_rod * s0)
        return gamma * P_ref * (A_cap * A_cap / V_cap + A_rod * A_rod / V_rod)

    k_pneu = gas_k(A1_cap, A1_rod) + gas_k(A2_cap, A2_rod)

    # total corner stiffness (proxy, identical corners)
    k_corner = max(0.0, k_tire + k_spring + k_pneu)

    # roll/pitch stiffness proxies
    # sum y^2 across 4 corners = track^2
    # sum x^2 across 4 corners = wheelbase^2
    Kphi = k_corner * (track * track)
    Ktheta = k_corner * (wheelbase * wheelbase)

    w_roll = math.sqrt(max(0.0, Kphi / max(I_roll, 1e-9)))
    w_pitch = math.sqrt(max(0.0, Ktheta / max(I_pitch, 1e-9)))

    f_roll = w_roll / (2.0 * math.pi)
    f_pitch = w_pitch / (2.0 * math.pi)

    # static deflection proxy
    m_total = float(params.get("масса_полная", m_body + 4.0 * float(params.get("масса_неподрессоренная_на_угол", 15.0))))
    z_static = (m_total * g) / max(4.0 * k_corner, 1e-9)

    return {
        "wheelbase": wheelbase,
        "track": track,
        "h_cg": h_cg,
        "phi_crit_rad": phi_crit,
        "theta_crit_rad": theta_crit,
        "phi_crit_deg": phi_crit * 180.0 / math.pi,
        "theta_crit_deg": theta_crit * 180.0 / math.pi,
        "k_tire": k_tire,
        "k_spring": k_spring,
        "k_pneumo": k_pneu,
        "k_corner": k_corner,
        "Kphi": Kphi,
        "Ktheta": Ktheta,
        "f_roll": f_roll,
        "f_pitch": f_pitch,
        "z_static": z_static,
    }


def _param_group(name: str) -> str:
    s = str(name).lower()
    pneumo_kw = ["объём", "давление", "клапан", "ресив", "аккумуля", "iso", "откры", "дроссел", "сброс"]
    kin_kw = ["база", "колея", "центр", "масс", "рама", "пружин", "шина", "ход_штока", "диаметр", "штока", "поршня", "инер"]
    if any(k in s for k in kin_kw):
        return "kinematics"
    if any(k in s for k in pneumo_kw):
        return "pneumatics"
    return "other"


def _numeric_params_from_ranges(ranges: Dict[str, Any]) -> List[str]:
    out = []
    for k, v in ranges.items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            out.append(str(k))
    return out


def build_pneumo_graph(mod, params: Dict[str, Any], p_up_ref: float, p_dn_ref: float) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Возвращает базовые метрики пневмосети, edges_df, paths_df."""
    if not hasattr(mod, "build_network_full"):
        raise RuntimeError("Модель не содержит build_network_full(params)")

    nodes, node_index, edges, _B = mod.build_network_full(params)

    # sources by name
    source_names = ["Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор"]
    sources = [node_index[n] for n in source_names if n in node_index]

    # chambers
    if isinstance(nodes, dict):
        chambers = [(name, int(node_index[name])) for name, nd in nodes.items() if str((nd or {}).get("kind") or "") == "chamber"]
    else:
        chambers = [
            (str(getattr(nd, "name", f"node_{i}")), int(i))
            for i, nd in enumerate(nodes or [])
            if str(getattr(nd, "kind", "") or "") == "chamber"
        ]

    iso_beta_lam = float(params.get("ISO_beta_lam", getattr(mod, "ISO6358_BETA_LAM_DEFAULT", 0.999)))
    dp_width = float(params.get("клапан_dp_переход_Па", 500.0))

    edges_info: List[EdgeInfo] = []
    cap: Dict[int, float] = {}
    adj: Dict[int, List[Tuple[int, int]]] = {}

    for ei, e in enumerate(edges):
        name = str(getattr(e, "name", f"E{ei}"))
        kind = str(getattr(e, "kind", ""))
        group = str(getattr(e, "group", ""))
        C_iso = _safe_float(getattr(e, "C_iso", None))
        b_iso = _safe_float(getattr(e, "b_iso", None))
        m_iso = _safe_float(getattr(e, "m_iso", None))
        A = float(getattr(e, "A", 0.0) or 0.0)
        Cd = float(getattr(e, "Cd", 0.8) or 0.8)
        dp_crack = float(getattr(e, "dp_crack", 0.0) or 0.0)

        mdot = 0.0
        try:
            if C_iso is not None and C_iso > 0:
                # account for crack threshold in a cheap way
                if (p_up_ref - p_dn_ref) <= dp_crack:
                    mdot = 0.0
                else:
                    p_eff = max(p_dn_ref, p_up_ref - dp_crack)
                    mdot = float(mod.mdot_iso6358(p_eff, p_dn_ref, C_iso, b=b_iso or 0.5, m=m_iso or 0.5, beta_lam=iso_beta_lam, T_up=getattr(mod, "T_ANR", 293.15)))
            else:
                mdot = float(mod.mdot_orifice(p_up_ref, p_dn_ref, A, T_up=getattr(mod, "T_ANR", 293.15), Cd=Cd, gamma=getattr(mod, "GAMMA", 1.4)))
        except Exception:
            mdot = 0.0

        mdot = float(mdot) if math.isfinite(float(mdot)) else 0.0
        cap[ei] = max(0.0, mdot)

        edges_info.append(EdgeInfo(
            idx=ei,
            name=name,
            n1=int(getattr(e, "n1")),
            n2=int(getattr(e, "n2")),
            kind=kind,
            group=group,
            C_iso=C_iso,
            b_iso=b_iso,
            m_iso=m_iso,
            A=A,
            Cd=Cd,
            dp_crack=dp_crack,
            mdot_ref=cap[ei],
        ))

        # undirected adjacency for influence
        adj.setdefault(int(getattr(e, "n1")), []).append((int(getattr(e, "n2")), ei))
        adj.setdefault(int(getattr(e, "n2")), []).append((int(getattr(e, "n1")), ei))

    # edge df
    edf = pd.DataFrame([{
        "edge_idx": x.idx,
        "edge": x.name,
        "kind": x.kind,
        "group": x.group,
        "n1": x.n1,
        "n2": x.n2,
        "C_iso": x.C_iso,
        "b_iso": x.b_iso,
        "m_iso": x.m_iso,
        "A": x.A,
        "Cd": x.Cd,
        "dp_crack": x.dp_crack,
        "mdot_ref": x.mdot_ref,
    } for x in edges_info])

    # paths
    rows = []
    bottlenecks: List[float] = []
    for cname, cidx in chambers:
        best_b = 0.0
        best_src = None
        best_edges: List[int] = []
        for sidx in sources:
            b, path_edges = widest_path(adj, cap, sidx, cidx)
            if b > best_b:
                best_b = b
                best_src = sidx
                best_edges = path_edges
        bottlenecks.append(best_b)
        # determine bottleneck edge
        bott_e = None
        bott_cap = None
        if best_edges:
            caps = [(ei, cap.get(ei, 0.0)) for ei in best_edges]
            bott_e, bott_cap = min(caps, key=lambda t: t[1])

        rows.append({
            "chamber": cname,
            "chamber_idx": cidx,
            "best_source_idx": best_src,
            "path_edges": ";".join(str(ei) for ei in best_edges),
            "bottleneck_edge_idx": bott_e,
            "bottleneck_mdot": bott_cap,
            "path_bottleneck_mdot": best_b,
        })

    pdf = pd.DataFrame(rows)
    min_bottleneck = float(np.min(bottlenecks)) if bottlenecks else 0.0
    avg_bottleneck = float(np.mean(bottlenecks)) if bottlenecks else 0.0

    metrics = {
        "p_up_ref": float(p_up_ref),
        "p_dn_ref": float(p_dn_ref),
        "n_edges": int(len(edges_info)),
        "n_chambers": int(len(chambers)),
        "min_bottleneck_mdot": min_bottleneck,
        "avg_bottleneck_mdot": avg_bottleneck,
    }
    return metrics, edf, pdf


def _finite_elasticity(val0: float, val1: float, p0: float, p1: float) -> float:
    """E = d ln(val) / d ln(p) via finite diff (p0->p1)."""
    if not (math.isfinite(val0) and math.isfinite(val1) and math.isfinite(p0) and math.isfinite(p1)):
        return 0.0
    if val0 <= 0 or val1 <= 0:
        return 0.0
    if p0 == 0 or p1 == 0:
        return 0.0
    try:
        return math.log(val1 / val0) / math.log(p1 / p0)
    except Exception:
        return 0.0


DEFAULT_ADAPTIVE_EPS_GRID: tuple[float, ...] = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2)


def _parse_eps_grid(raw: str | None, *, requested_eps_rel: float | None = None) -> List[float]:
    vals: List[float] = []
    if isinstance(raw, str) and raw.strip():
        for chunk in raw.replace(";", ",").split(","):
            piece = chunk.strip()
            if not piece:
                continue
            try:
                v = float(piece)
            except Exception:
                continue
            if math.isfinite(v) and v > 0.0:
                vals.append(float(v))
    if requested_eps_rel is not None:
        try:
            req = float(requested_eps_rel)
        except Exception:
            req = 0.0
        if math.isfinite(req) and req > 0.0:
            vals.append(float(req))
    if not vals:
        vals = list(DEFAULT_ADAPTIVE_EPS_GRID)
    uniq: List[float] = []
    for v in sorted(vals):
        if not uniq or abs(v - uniq[-1]) > 1e-15:
            uniq.append(float(v))
    return uniq


def _build_perturbed_value(x0: float, eps_rel: float) -> Tuple[float, float]:
    eps = max(float(eps_rel), 1e-12)
    dp = eps * max(abs(x0), 1.0)
    if (not math.isfinite(dp)) or dp == 0.0:
        dp = eps
    x1 = x0 + dp
    if x0 > 0.0 and x1 <= 0.0:
        x1 = x0 * (1.0 + eps)
    elif x0 < 0.0 and x1 >= 0.0:
        x1 = x0 * (1.0 + eps)
    return float(x1), float(x1 - x0)


def _elasticity_map(flat0: Dict[str, float], flat1: Dict[str, float], x0: float, x1: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for mk, v0m in flat0.items():
        v1m = float(flat1.get(mk, 0.0))
        out[f"elas_{mk}"] = float(_finite_elasticity(float(v0m), v1m, float(x0), float(x1)))
    return out


def _select_adaptive_eps_candidate(
    candidates: List[Dict[str, Any]],
    *,
    requested_eps_rel: float,
    strategy: str = "balanced",
) -> Dict[str, Any]:
    if not candidates:
        return {}
    requested = max(float(requested_eps_rel), 1e-12)
    strategy_key = str(strategy or "balanced").strip().lower()
    metric_names = sorted({
        str(k)
        for rec in candidates
        for k, v in dict(rec.get("elasticities") or {}).items()
        if isinstance(k, str) and math.isfinite(float(v))
    })
    if not metric_names:
        chosen = dict(candidates[0])
        chosen["adaptive_stability_loss"] = 0.0
        chosen["adaptive_metric_count"] = 0
        return chosen

    medians: Dict[str, float] = {}
    for mk in metric_names:
        vals = []
        for rec in candidates:
            try:
                vals.append(float(dict(rec.get("elasticities") or {}).get(mk)))
            except Exception:
                continue
        vals = [v for v in vals if math.isfinite(v)]
        if vals:
            medians[mk] = float(np.median(np.asarray(vals, dtype=float)))

    scored: List[Dict[str, Any]] = []
    for rec in candidates:
        elas = dict(rec.get("elasticities") or {})
        diffs: List[float] = []
        finite_count = 0
        for mk, med in medians.items():
            try:
                val = float(elas.get(mk))
            except Exception:
                continue
            if not math.isfinite(val):
                continue
            finite_count += 1
            diffs.append(abs(val - med) / (1.0 + abs(med)))
        stability_loss = float(np.mean(np.asarray(diffs, dtype=float))) if diffs else float("inf")
        eps_val = max(float(rec.get("eps_rel", requested)), 1e-12)
        requested_loss = abs(math.log10(eps_val) - math.log10(requested))
        row = dict(rec)
        row["adaptive_stability_loss"] = 0.0 if not math.isfinite(stability_loss) else float(stability_loss)
        row["adaptive_metric_count"] = int(finite_count)
        row["_adaptive_requested_loss"] = float(requested_loss)
        scored.append(row)

    max_metric_count = max(int(rec.get("adaptive_metric_count", 0) or 0) for rec in scored)
    scored = [rec for rec in scored if int(rec.get("adaptive_metric_count", 0) or 0) == max_metric_count]
    min_stability = min(float(rec.get("adaptive_stability_loss", float("inf")) or float("inf")) for rec in scored)
    tolerance = max(1e-6, min_stability * 0.10)
    stable_shortlist = [
        rec for rec in scored
        if float(rec.get("adaptive_stability_loss", float("inf")) or float("inf")) <= (min_stability + tolerance)
    ]
    def _strategy_sort_key(rec: Dict[str, Any]) -> tuple[float, float, float]:
        eps_val = max(float(rec.get("eps_rel", requested)), 1e-12)
        requested_loss = float(rec.get("_adaptive_requested_loss", float("inf")))
        stability_loss = float(rec.get("adaptive_stability_loss", float("inf")))
        if strategy_key == "coarse":
            return (-eps_val, requested_loss, stability_loss)
        if strategy_key == "fine":
            return (eps_val, requested_loss, stability_loss)
        return (
            requested_loss,
            stability_loss,
            abs(float(rec.get("eps_rel", requested)) - requested),
        )

    stable_shortlist.sort(key=_strategy_sort_key)
    chosen = dict(stable_shortlist[0] if stable_shortlist else scored[0])
    chosen.pop("_adaptive_requested_loss", None)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description="System Influence report (pneumatics + kinematics)")
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--model", default="", help="path to model.py (optional; auto from AUTOPILOT meta)")
    ap.add_argument("--base_json", default="", help="override base_json (optional)")
    ap.add_argument("--fit_ranges_json", default="", help="override fit_ranges_json (optional)")
    ap.add_argument("--p_up_ref", type=float, default=0.0, help="reference upstream abs pressure for mdot_ref")
    ap.add_argument("--p_dn_ref", type=float, default=0.0, help="reference downstream abs pressure for mdot_ref")
    ap.add_argument("--eps_rel", type=float, default=1e-2, help="relative perturbation for elasticity")
    ap.add_argument("--adaptive_eps", action="store_true", help="scan a small eps_rel grid and choose the most stable local elasticity per parameter")
    ap.add_argument("--adaptive_eps_grid", default="1e-4,3e-4,1e-3,3e-3,1e-2", help="comma-separated eps_rel grid for --adaptive_eps")
    ap.add_argument("--adaptive_eps_strategy", choices=["balanced", "coarse", "fine"], default="balanced", help="tie-break strategy inside the stable adaptive epsilon shortlist")
    ap.add_argument("--stage_name", default="", help="optional runtime stage label for diagnostics (stage0_relevance / stage1_long / stage2_final)")
    ap.add_argument("--max_params", type=int, default=200, help="safety limit")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"run_dir not found: {run_dir}")

    ROOT = Path(__file__).resolve().parents[1]

    # resolve meta (v19 wrapper preferred)
    meta = {}
    meta_p = run_dir / "AUTOPILOT_V19_WRAPPER.json"
    if meta_p.exists():
        try:
            meta = _load_json(meta_p)
        except Exception:
            meta = {}

    # resolve model
    model_rel = str(args.model).strip() or str(meta.get("model") or "").strip() or "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"
    model_p = Path(model_rel)
    if not model_p.is_absolute():
        model_p = (ROOT / model_rel).resolve()
    if not model_p.exists():
        raise SystemExit(f"Model file not found: {model_p}")

    # resolve base
    base_override = str(args.base_json).strip()
    base_p: Optional[Path] = None
    if base_override:
        base_p = Path(base_override)
        if not base_p.is_absolute():
            base_p = (ROOT / base_override).resolve()
    else:
        # prefer tradeoff_selected_base if exists
        for cand in [
            run_dir / "tradeoff_selected_base.json",
            run_dir / "pareto_tradeoff" / "pareto_selected_base.json",
            run_dir / "epsilon_tradeoff" / "epsilon_selected_base.json",
            run_dir / "fitted_base_final.json",
        ]:
            if cand.exists():
                base_p = cand
                break
        if base_p is None:
            # fallback to meta base_json
            meta_base = str(meta.get("base_json") or "default_base.json")
            bp = Path(meta_base)
            if not bp.is_absolute():
                bp = (ROOT / meta_base).resolve()
            base_p = bp

    if base_p is None or not base_p.exists():
        raise SystemExit(f"base_json not found: {base_p}")

    params: Dict[str, Any] = _load_json(base_p)

    # resolve fit_ranges
    ranges_override = str(args.fit_ranges_json).strip()
    ranges_p: Optional[Path] = None
    if ranges_override:
        rp = Path(ranges_override)
        if not rp.is_absolute():
            rp = (ROOT / ranges_override).resolve()
        ranges_p = rp
    else:
        # if param_prune produced pruned ranges — prefer it
        cand = run_dir / "param_prune" / "fit_ranges_pruned.json"
        if cand.exists():
            ranges_p = cand
        else:
            meta_ranges = str(meta.get("fit_ranges_json") or "default_ranges.json")
            rp = Path(meta_ranges)
            if not rp.is_absolute():
                rp = (ROOT / meta_ranges).resolve()
            ranges_p = rp

    fit_ranges: Dict[str, Any] = {}
    if ranges_p and ranges_p.exists():
        try:
            fit_ranges = _load_json(ranges_p)
        except Exception:
            fit_ranges = {}

    # param list to analyse
    param_list: List[str] = []
    if fit_ranges:
        param_list.extend(_numeric_params_from_ranges(fit_ranges))

    # Always include key kinematics params even if not in ranges
    extra_kin = [
        "база",
        "колея",
        "высота_центра_масс",
        "масса_рамы",
        "масса_неподрессоренная_на_угол",
        "жёсткость_шины",
        "демпфирование_шины",
        "пружина_масштаб",
        "ход_штока",
        "диаметр_поршня_Ц1",
        "диаметр_штока_Ц1",
        "диаметр_поршня_Ц2",
        "диаметр_штока_Ц2",
        "мёртвый_объём_камеры",
    ]
    for k in extra_kin:
        if k not in param_list:
            param_list.append(k)

    # safety cap
    param_list = param_list[: int(args.max_params)]

    # load model module
    mod = load_py_module(model_p, module_name=f"model_influence_{int(time.time())}")

    # reference pressures
    P_ATM = float(getattr(mod, "P_ATM", 101325.0))
    if args.p_up_ref > 0:
        p_up_ref = float(args.p_up_ref)
    else:
        # use a few setpoints if present
        cand_ps = []
        for k in [
            "давление_Pmid_сброс",
            "давление_Pmin_питание_Ресивер2",
            "давление_Pmax_питание_Ресивер3",
            "давление_Pзаряд_аккумулятора_из_Ресивер3",
            "начальное_давление_аккумулятора",
        ]:
            v = _safe_float(params.get(k))
            if v is not None and v > 0:
                cand_ps.append(v)
        p_up_ref = max(cand_ps) if cand_ps else (P_ATM + 5e5)
    if args.p_dn_ref > 0:
        p_dn_ref = float(args.p_dn_ref)
    else:
        p_dn_ref = P_ATM

    # baseline metrics
    pneumo_metrics0, edges_df0, paths_df0 = build_pneumo_graph(mod, params, p_up_ref=p_up_ref, p_dn_ref=p_dn_ref)

    # store P_ATM in params to compute mech proxies in a consistent way
    params_for_mech = dict(params)
    params_for_mech["P_ATM"] = P_ATM

    mech0 = compute_mech_proxies(params_for_mech)

    baseline = {
        "base_json": str(base_p),
        "model": str(model_p),
        "fit_ranges_json": str(ranges_p) if ranges_p else None,
        "pneumo": pneumo_metrics0,
        "mech": mech0,
    }

    # sensitivity per parameter
    eps_rel = float(args.eps_rel)
    adaptive_eps = bool(args.adaptive_eps)
    adaptive_eps_strategy = str(args.adaptive_eps_strategy or "balanced").strip().lower() or "balanced"
    stage_name = str(args.stage_name or "").strip()
    adaptive_eps_grid = _parse_eps_grid(str(args.adaptive_eps_grid or ""), requested_eps_rel=eps_rel) if adaptive_eps else [float(eps_rel)]

    sens_rows = []
    adaptive_eps_selected_counts: Dict[str, int] = {}

    # choose a small set of metrics for scoring
    def combined_score(el: Dict[str, float]) -> float:
        # weights: pneumo bottleneck + roll/pitch stiffness + stability angles
        w = {
            "elas_min_bottleneck_mdot": 1.0,
            "elas_Kphi": 0.5,
            "elas_Ktheta": 0.5,
            "elas_phi_crit_deg": 0.2,
            "elas_theta_crit_deg": 0.2,
            "elas_f_roll": 0.3,
            "elas_f_pitch": 0.3,
        }
        s = 0.0
        for k, wk in w.items():
            s += wk * abs(float(el.get(k, 0.0) or 0.0))
        return float(s)

    # helper to eval metrics for perturbed params
    def eval_metrics(pdict: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float]]:
        pneumo_m, _edf, _pdf = build_pneumo_graph(mod, pdict, p_up_ref=p_up_ref, p_dn_ref=p_dn_ref)
        pd2 = dict(pdict)
        pd2["P_ATM"] = P_ATM
        mech_m = compute_mech_proxies(pd2)
        # flatten
        flat = {
            "min_bottleneck_mdot": float(pneumo_m.get("min_bottleneck_mdot", 0.0)),
            "avg_bottleneck_mdot": float(pneumo_m.get("avg_bottleneck_mdot", 0.0)),
            "Kphi": float(mech_m.get("Kphi", 0.0)),
            "Ktheta": float(mech_m.get("Ktheta", 0.0)),
            "phi_crit_deg": float(mech_m.get("phi_crit_deg", 0.0)),
            "theta_crit_deg": float(mech_m.get("theta_crit_deg", 0.0)),
            "f_roll": float(mech_m.get("f_roll", 0.0)),
            "f_pitch": float(mech_m.get("f_pitch", 0.0)),
        }
        return pneumo_m, flat

    # baseline flat
    pneumo0 = pneumo_metrics0
    flat0 = {
        "min_bottleneck_mdot": float(pneumo0.get("min_bottleneck_mdot", 0.0)),
        "avg_bottleneck_mdot": float(pneumo0.get("avg_bottleneck_mdot", 0.0)),
        "Kphi": float(mech0.get("Kphi", 0.0)),
        "Ktheta": float(mech0.get("Ktheta", 0.0)),
        "phi_crit_deg": float(mech0.get("phi_crit_deg", 0.0)),
        "theta_crit_deg": float(mech0.get("theta_crit_deg", 0.0)),
        "f_roll": float(mech0.get("f_roll", 0.0)),
        "f_pitch": float(mech0.get("f_pitch", 0.0)),
    }

    for pname in param_list:
        v0 = params.get(pname)
        x0 = _safe_float(v0)
        if x0 is None:
            # if missing numeric default, skip sensitivity but still include in table
            sens_rows.append({
                "param": pname,
                "group": _param_group(pname),
                "value": v0,
                "status": "non_numeric_or_missing",
                "score": 0.0,
            })
            continue

        candidate_rows: List[Dict[str, Any]] = []
        for eps_candidate in adaptive_eps_grid:
            x1, dp = _build_perturbed_value(float(x0), float(eps_candidate))
            p1 = dict(params)
            p1[pname] = float(x1)
            try:
                _pneumo1, flat1 = eval_metrics(p1)
            except Exception:
                continue
            candidate_rows.append({
                "eps_rel": float(eps_candidate),
                "x1": float(x1),
                "dp": float(dp),
                "elasticities": _elasticity_map(flat0, flat1, float(x0), float(x1)),
            })

        if not candidate_rows:
            sens_rows.append({
                "param": pname,
                "group": _param_group(pname),
                "value": x0,
                "status": "eval_failed",
                "score": 0.0,
                "eps_mode": "adaptive" if adaptive_eps else "fixed",
                "eps_rel_used": float(eps_rel),
            })
            continue

        selected = _select_adaptive_eps_candidate(
            candidate_rows,
            requested_eps_rel=float(eps_rel),
            strategy=adaptive_eps_strategy,
        ) if adaptive_eps else dict(candidate_rows[0])
        elas = dict(selected.get("elasticities") or {})
        score = combined_score(elas)
        selected_eps = float(selected.get("eps_rel", eps_rel))
        adaptive_eps_selected_counts[f"{selected_eps:.6g}"] = int(adaptive_eps_selected_counts.get(f"{selected_eps:.6g}", 0)) + 1

        row = {
            "param": pname,
            "group": _param_group(pname),
            "value": float(x0),
            "dp": float(selected.get("dp", 0.0) or 0.0),
            "eps_rel_used": float(selected_eps),
            "eps_mode": "adaptive" if adaptive_eps else "fixed",
            "adaptive_candidate_count": int(len(candidate_rows)),
            "adaptive_stability_loss": float(selected.get("adaptive_stability_loss", 0.0) or 0.0),
            **elas,
            "score": float(score),
            "status": "ok",
        }

        # if the param is in fit_ranges, add bounds
        if pname in fit_ranges and isinstance(fit_ranges[pname], (list, tuple)) and len(fit_ranges[pname]) == 2:
            row["lo"] = fit_ranges[pname][0]
            row["hi"] = fit_ranges[pname][1]

        sens_rows.append(row)

    df_params = pd.DataFrame(sens_rows)
    if "score" in df_params.columns:
        df_params = df_params.sort_values("score", ascending=False)

    # write artifacts
    out_json = {
        "version": "system_influence_report_v1",
        "ts": time.time(),
        "config": {
            "requested_eps_rel": float(eps_rel),
            "adaptive_eps": bool(adaptive_eps),
            "adaptive_eps_grid": [float(x) for x in adaptive_eps_grid],
            "adaptive_eps_strategy": str(adaptive_eps_strategy),
            "adaptive_selection": f"median_elasticity_stability_then_{adaptive_eps_strategy}",
            "stage_name": stage_name or None,
        },
        "baseline": baseline,
        "adaptive_summary": {
            "selected_eps_counts": adaptive_eps_selected_counts,
        },
        "params": df_params.to_dict(orient="records"),
    }

    _save_json(out_json, run_dir / "system_influence.json")
    _save_csv(df_params, run_dir / "system_influence_params.csv")
    _save_csv(edges_df0, run_dir / "system_influence_edges.csv")
    _save_csv(paths_df0, run_dir / "system_influence_paths.csv")

    # markdown report
    md: List[str] = []
    md.append("# System Influence (pneumatics + kinematics)\n")
    md.append(f"Run dir: `{run_dir.name}`  ")
    if stage_name:
        md.append(f"Stage: `{stage_name}`  ")
    md.append(f"Model: `{model_p.name}`  ")
    md.append(f"Base: `{Path(base_p).name}`  ")
    if ranges_p:
        md.append(f"Ranges: `{Path(ranges_p).name}`  ")
    md.append("")

    md.append("## Sensitivity config\n")
    md.append(f"- requested eps_rel: `{_fmt(eps_rel, nd=6)}`")
    md.append(f"- adaptive_eps: `{bool(adaptive_eps)}`")
    md.append(f"- adaptive_eps_strategy: `{adaptive_eps_strategy}`")
    md.append(f"- adaptive_eps_grid: `{', '.join(_fmt(x, nd=6) for x in adaptive_eps_grid)}`")
    if adaptive_eps_selected_counts:
        md.append(f"- selected eps counts: `{adaptive_eps_selected_counts}`")
    md.append("")

    md.append("## Baseline metrics\n")
    md.append("### Pneumatics (network proxy)")
    for k in ["p_up_ref", "p_dn_ref", "n_edges", "n_chambers", "min_bottleneck_mdot", "avg_bottleneck_mdot"]:
        if k in pneumo_metrics0:
            md.append(f"- {k}: `{_fmt(pneumo_metrics0.get(k))}`")
    md.append("")

    md.append("### Kinematics/geometry (proxy)")
    for k in [
        "wheelbase",
        "track",
        "h_cg",
        "phi_crit_deg",
        "theta_crit_deg",
        "k_corner",
        "Kphi",
        "Ktheta",
        "f_roll",
        "f_pitch",
        "z_static",
    ]:
        if k in mech0:
            md.append(f"- {k}: `{_fmt(mech0.get(k))}`")
    md.append("")

    md.append("## Bottleneck edges (top 15 by mdot_ref)\n")
    if not edges_df0.empty:
        ed = edges_df0.sort_values("mdot_ref", ascending=False).head(15)
        md.append("| edge | kind | group | mdot_ref | C_iso | A | dp_crack |")
        md.append("|---|---|---|---:|---:|---:|---:|")
        for _, r in ed.iterrows():
            md.append(
                f"| {r.get('edge')} | {r.get('kind')} | {r.get('group')} | {_fmt(r.get('mdot_ref'))} | {_fmt(r.get('C_iso'))} | {_fmt(r.get('A'))} | {_fmt(r.get('dp_crack'))} |"
            )
        md.append("")
    else:
        md.append("(edges not available)\n")

    md.append("## Paths to chambers (widest path)\n")
    if not paths_df0.empty:
        pdx = paths_df0.sort_values("path_bottleneck_mdot", ascending=True).head(20)
        md.append("| chamber | bottleneck_edge_idx | path_bottleneck_mdot |")
        md.append("|---|---:|---:|")
        for _, r in pdx.iterrows():
            md.append(f"| {r.get('chamber')} | {r.get('bottleneck_edge_idx')} | {_fmt(r.get('path_bottleneck_mdot'))} |")
        md.append("")
        md.append("Полная таблица: `system_influence_paths.csv`\n")

    md.append("## Parameter influence ranking (top 25)\n")
    if not df_params.empty:
        top = df_params[df_params.get("status", "") == "ok"].head(25)
        md.append(
            "| param | group | score | E[min_bottleneck] | E[Kphi] | E[Ktheta] | E[phi_crit] | E[f_roll] |"
        )
        md.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for _, r in top.iterrows():
            md.append(
                "| {p} | {g} | {s} | {e1} | {e2} | {e3} | {e4} | {e5} |".format(
                    p=r.get("param"),
                    g=r.get("group"),
                    s=_fmt(r.get("score"), nd=4),
                    e1=_fmt(r.get("elas_min_bottleneck_mdot"), nd=4),
                    e2=_fmt(r.get("elas_Kphi"), nd=4),
                    e3=_fmt(r.get("elas_Ktheta"), nd=4),
                    e4=_fmt(r.get("elas_phi_crit_deg"), nd=4),
                    e5=_fmt(r.get("elas_f_roll"), nd=4),
                )
            )
        md.append("")

        md.append("**Примечание по эластичности:** E=1 означает: +1% параметра → примерно +1% метрики (локально).\n")
    else:
        md.append("(no params)\n")

    md.append("## Files\n")
    md.append("- system_influence.json")
    md.append("- system_influence_params.csv")
    md.append("- system_influence_edges.csv")
    md.append("- system_influence_paths.csv")
    md.append("")

    _save_text("\n".join(md), run_dir / "SYSTEM_INFLUENCE.md")

    print(f"[OK] System influence report written to: {run_dir}")


if __name__ == "__main__":
    main()
