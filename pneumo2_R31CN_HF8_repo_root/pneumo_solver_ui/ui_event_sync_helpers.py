from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, MutableMapping


SessionState = MutableMapping[str, Any]


def consume_svg_pick_event(
    session_state: SessionState,
    apply_pick_list_fn: Callable[[Any, str, str], list[str]],
) -> None:
    """Consume last pick event from the SVG component and sync other widgets."""
    evt = session_state.get("svg_pick_event")
    if not isinstance(evt, dict):
        return

    ts = evt.get("ts")
    last_ts = session_state.get("svg_pick_event_last_ts")
    if ts is not None and ts == last_ts:
        return
    session_state["svg_pick_event_last_ts"] = ts

    kind = evt.get("kind")
    name = evt.get("name")
    if not isinstance(name, str) or not name.strip():
        return
    name = name.strip()
    if kind not in ("edge", "node", "label", "review_nav", "review_filter", "review_toggle"):
        return

    try:
        if kind == "edge":
            ra = evt.get("review_action")
            if isinstance(ra, str):
                ra = ra.strip().lower()
            if ra in ("approved", "pending", "rejected"):
                mapping_text = session_state.get("svg_mapping_text", "")
                if isinstance(mapping_text, str) and mapping_text.strip():
                    try:
                        mobj = json.loads(mapping_text)
                    except Exception:
                        mobj = None
                    if isinstance(mobj, dict):
                        mobj.setdefault("version", 2)
                        mobj.setdefault("edges", {})
                        mobj.setdefault("nodes", {})
                        mobj.setdefault("edges_meta", {})
                        if not isinstance(mobj.get("edges_meta"), dict):
                            mobj["edges_meta"] = {}
                        em = mobj["edges_meta"].get(name, {})
                        if not isinstance(em, dict):
                            em = {}
                        em.setdefault("review", {})
                        if not isinstance(em.get("review"), dict):
                            em["review"] = {}
                        em["review"]["status"] = ra
                        em["review"]["by"] = str(evt.get("via", "svg"))
                        em["review"]["ts"] = float(time.time())
                        if isinstance(evt.get("note"), str) and evt.get("note").strip():
                            em["review"]["note"] = evt.get("note").strip()
                        mobj["edges_meta"][name] = em
                        session_state["svg_mapping_text"] = json.dumps(mobj, ensure_ascii=False, indent=2)
                        session_state["svg_review_last"] = {"edge": name, "status": ra, "ts": float(time.time())}
    except Exception:
        pass

    if kind == "review_toggle":
        try:
            session_state["svg_show_review_overlay"] = bool(evt.get("value"))
        except Exception:
            pass
        return

    if kind == "review_filter":
        try:
            mode = str(evt.get("mode") or "").strip()
        except Exception:
            mode = ""
        if mode == "toggle_pending_only":
            try:
                cur = session_state.get("svg_review_statuses", ["approved", "pending", "rejected"])
                cur_set = set([str(x) for x in cur]) if isinstance(cur, (list, tuple)) else set()
                if cur_set and cur_set.issubset({"pending", "unknown"}):
                    session_state["svg_review_statuses"] = ["approved", "pending", "rejected"]
                else:
                    session_state["svg_review_statuses"] = ["pending", "unknown"]
                session_state["svg_show_review_overlay"] = True
            except Exception:
                pass
            return

    if kind == "review_nav":
        try:
            action = str(evt.get("action") or "").strip()
        except Exception:
            action = ""
        if action in ("next_pending", "prev_pending"):
            try:
                mapping_text = session_state.get("svg_mapping_text", "")
                mobj = json.loads(mapping_text) if isinstance(mapping_text, str) and mapping_text.strip() else {}
            except Exception:
                mobj = {}
            pending: list[str] = []
            try:
                edges_geo = mobj.get("edges", {}) if isinstance(mobj, dict) else {}
                emap = mobj.get("edges_meta", {}) if isinstance(mobj, dict) else {}
                if not isinstance(edges_geo, dict):
                    edges_geo = {}
                if not isinstance(emap, dict):
                    emap = {}
                for e_name, segs in edges_geo.items():
                    if not isinstance(segs, list) or not segs:
                        continue
                    status = "unknown"
                    try:
                        meta = emap.get(str(e_name), {})
                        rv = meta.get("review", {}) if isinstance(meta, dict) else {}
                        stt = rv.get("status", "") if isinstance(rv, dict) else ""
                        status = str(stt) if stt else "unknown"
                    except Exception:
                        status = "unknown"
                    if status in ("pending", "unknown", ""):
                        pending.append(str(e_name))
                pending = sorted(set(pending))
            except Exception:
                pending = []
            if pending:
                cur = str(session_state.get("svg_selected_edge") or "")
                i = pending.index(cur) if cur in pending else -1
                if action == "next_pending":
                    j = (i + 1) if (i + 1) < len(pending) else 0
                else:
                    j = (i - 1) if i > 0 else (len(pending) - 1)
                session_state["svg_selected_edge"] = pending[j]
                session_state["svg_selected_node"] = ""
            return

    try:
        if kind == "edge":
            ra = evt.get("review_action")
            ra2 = ra.strip().lower() if isinstance(ra, str) else ""
            if ra2 in ("approved", "rejected") and bool(session_state.get("svg_review_auto_advance", True)):
                try:
                    mapping_text = session_state.get("svg_mapping_text", "")
                    mobj = json.loads(mapping_text) if isinstance(mapping_text, str) and mapping_text.strip() else {}
                except Exception:
                    mobj = {}
                pending: list[str] = []
                try:
                    edges_geo = mobj.get("edges", {}) if isinstance(mobj, dict) else {}
                    emap = mobj.get("edges_meta", {}) if isinstance(mobj, dict) else {}
                    if not isinstance(edges_geo, dict):
                        edges_geo = {}
                    if not isinstance(emap, dict):
                        emap = {}
                    for e_name, segs in edges_geo.items():
                        if not isinstance(segs, list) or not segs:
                            continue
                        status = "unknown"
                        try:
                            meta = emap.get(str(e_name), {})
                            rv = meta.get("review", {}) if isinstance(meta, dict) else {}
                            stt = rv.get("status", "") if isinstance(rv, dict) else ""
                            status = str(stt) if stt else "unknown"
                        except Exception:
                            status = "unknown"
                        if status in ("pending", "unknown", ""):
                            pending.append(str(e_name))
                    pending = sorted(set(pending))
                except Exception:
                    pending = []
                if pending:
                    cur = str(session_state.get("svg_selected_edge") or "")
                    i = pending.index(cur) if cur in pending else -1
                    j = (i + 1) if (i + 1) < len(pending) else 0
                    session_state["svg_selected_edge"] = pending[j]
                    session_state["svg_selected_node"] = ""
    except Exception:
        pass

    if kind == "label":
        pmode = evt.get("mode")
        if pmode in ("start", "end"):
            session_state["svg_route_label_pick_pending"] = evt
            session_state["svg_label_pick_mode"] = ""
        return

    mode = session_state.get("svg_click_mode", "replace")
    if mode not in ("add", "replace"):
        mode = "add"

    if kind == "edge":
        session_state["svg_selected_edge"] = name
        session_state["flow_graph_edges"] = apply_pick_list_fn(session_state.get("flow_graph_edges"), name, mode)
        session_state["anim_edges_svg"] = apply_pick_list_fn(session_state.get("anim_edges_svg"), name, mode)

    if kind == "node":
        session_state["svg_selected_node"] = name
        session_state["anim_nodes_svg"] = apply_pick_list_fn(session_state.get("anim_nodes_svg"), name, mode)
        session_state["node_pressure_plot"] = apply_pick_list_fn(session_state.get("node_pressure_plot"), name, mode)


def consume_mech_pick_event(session_state: SessionState) -> None:
    """Consume last pick event from mechanical animation components (2D/3D) and sync widgets."""
    candidates = []
    for k in ("mech3d_pick_event", "mech2d_pick_event", "mech_pick_event"):
        evt_k = session_state.get(k)
        if isinstance(evt_k, dict):
            ts_k = evt_k.get("ts")
            try:
                ts_f = float(ts_k) if ts_k is not None else 0.0
            except Exception:
                ts_f = 0.0
            candidates.append((ts_f, 1 if k == "mech3d_pick_event" else 0, evt_k))
    if not candidates:
        return
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    evt = candidates[0][2]

    ts = evt.get("ts")
    last_ts = session_state.get("mech_pick_event_last_ts")
    if ts is not None and ts == last_ts:
        return
    session_state["mech_pick_event_last_ts"] = ts

    name = evt.get("name")
    if not isinstance(name, str) or not name.strip():
        return
    name = name.strip()

    mode = session_state.get("svg_click_mode", "replace")
    if mode not in ("add", "replace"):
        mode = "add"

    name_l = name.lower()
    if name in ("ко", "оо", "кг", "ог"):
        corners = [name]
    elif name_l in ("оепед", "front", "f", "оепеднй"):
        corners = ["ко", "оо"]
    elif name_l in ("гюд", "rear", "r", "гюднй"):
        corners = ["кг", "ог"]
    else:
        return

    cur_sel = session_state.get("mech_selected_corners")
    if not isinstance(cur_sel, list):
        cur_sel = []
    if mode == "replace":
        new_sel = list(dict.fromkeys(corners))
    else:
        new_sel = list(cur_sel)
        for c in corners:
            if c not in new_sel:
                new_sel.append(c)

    session_state["mech_selected_corners"] = new_sel
    session_state["mech_plot_corners"] = list(new_sel) if new_sel else session_state.get("mech_plot_corners", ["ко", "оо", "кг", "ог"])


def consume_plotly_pick_events(
    session_state: SessionState,
    extract_plotly_selection_points_fn: Callable[[Any], list[dict[str, Any]]],
    plotly_points_signature_fn: Callable[[list[dict[str, Any]]], str],
    apply_pick_list_fn: Callable[[Any, str, str], list[str]],
) -> None:
    """Sync Plotly chart selections -> SVG selection and animation defaults."""
    flow_key = "plot_flow_edges"
    flow_state = session_state.get(flow_key)
    flow_points = extract_plotly_selection_points_fn(flow_state)
    if flow_points:
        sig = plotly_points_signature_fn(flow_points)
        last_sig = session_state.get(flow_key + "__last_sig")
        if sig != last_sig:
            session_state[flow_key + "__last_sig"] = sig
            try:
                x0 = flow_points[0].get("x")
                if x0 is not None:
                    session_state["playhead_request_x"] = float(x0)
            except Exception:
                pass

            trace_names = session_state.get(flow_key + "__trace_names")
            if isinstance(trace_names, list) and trace_names:
                picked: list[str] = []
                for p in flow_points:
                    cn = p.get("curve_number", p.get("curveNumber"))
                    try:
                        ci = int(cn)
                    except Exception:
                        continue
                    if 0 <= ci < len(trace_names):
                        picked.append(str(trace_names[ci]))

                seen = set()
                picked_u = []
                for name in picked:
                    if name not in seen:
                        seen.add(name)
                        picked_u.append(name)

                if picked_u:
                    for name in picked_u:
                        session_state["svg_selected_edge"] = name
                        session_state["anim_edges_svg"] = apply_pick_list_fn(session_state.get("anim_edges_svg"), name, "add")

    node_key = "plot_node_pressure"
    node_state = session_state.get(node_key)
    node_points = extract_plotly_selection_points_fn(node_state)
    if node_points:
        sig = plotly_points_signature_fn(node_points)
        last_sig = session_state.get(node_key + "__last_sig")
        if sig != last_sig:
            session_state[node_key + "__last_sig"] = sig
            try:
                x0 = node_points[0].get("x")
                if x0 is not None:
                    session_state["playhead_request_x"] = float(x0)
            except Exception:
                pass

            trace_names = session_state.get(node_key + "__trace_names")
            if isinstance(trace_names, list) and trace_names:
                picked: list[str] = []
                for p in node_points:
                    cn = p.get("curve_number", p.get("curveNumber"))
                    try:
                        ci = int(cn)
                    except Exception:
                        continue
                    if 0 <= ci < len(trace_names):
                        picked.append(str(trace_names[ci]))

                seen = set()
                picked_u = []
                for name in picked:
                    if name not in seen:
                        seen.add(name)
                        picked_u.append(name)

                if picked_u:
                    for name in picked_u:
                        session_state["svg_selected_node"] = name
                        session_state["anim_nodes_svg"] = apply_pick_list_fn(session_state.get("anim_nodes_svg"), name, "add")
                        session_state["node_pressure_plot"] = apply_pick_list_fn(session_state.get("node_pressure_plot"), name, "add")


def consume_playhead_event(
    session_state: SessionState,
    persist_browser_perf_snapshot_event_fn: Callable[[dict[str, Any], Path], dict[str, Any] | None],
    workspace_exports_dir: Path,
    log_event_fn: Callable[..., None],
    proc_metrics_fn: Callable[[], dict[str, Any]],
) -> None:
    """Consume global playhead updates from the playhead_ctrl component."""
    evt = session_state.get("playhead_event")
    if not isinstance(evt, dict):
        return

    if evt.get("kind") == "browser_perf_snapshot":
        ts = evt.get("ts")
        last_perf_ts = session_state.get("playhead_browser_perf_last_ts")
        if ts is not None and ts == last_perf_ts:
            return
        session_state["playhead_browser_perf_last_ts"] = ts
        try:
            perf_summary = persist_browser_perf_snapshot_event_fn(evt, workspace_exports_dir)
        except Exception:
            perf_summary = None
        if isinstance(perf_summary, dict):
            session_state["browser_perf_summary"] = perf_summary
            try:
                log_event_fn(
                    "browser_perf_snapshot_exported",
                    dataset_id=str(perf_summary.get("browser_perf_dataset_id") or evt.get("dataset_id") or ""),
                    component_count=int(perf_summary.get("browser_perf_component_count") or 0),
                    total_wakeups=int(perf_summary.get("browser_perf_total_wakeups") or 0),
                    total_duplicate_guard_hits=int(perf_summary.get("browser_perf_total_duplicate_guard_hits") or 0),
                    trace_exists=bool(perf_summary.get("browser_perf_trace_exists")),
                    level=str(perf_summary.get("browser_perf_level") or ""),
                    proc=proc_metrics_fn(),
                )
            except Exception:
                pass
        return

    if evt.get("kind") not in (None, "playhead"):
        return

    ts = evt.get("ts")
    last_ts = session_state.get("playhead_event_last_ts")
    if ts is not None and ts == last_ts:
        return
    session_state["playhead_event_last_ts"] = ts

    ds = evt.get("dataset_id")
    if isinstance(ds, str):
        session_state["playhead_dataset_id"] = ds

    try:
        idx = int(evt.get("idx", 0))
    except Exception:
        idx = 0
    if idx < 0:
        idx = 0
    session_state["playhead_idx"] = idx

    try:
        t = float(evt.get("t", 0.0))
    except Exception:
        t = 0.0
    session_state["playhead_t"] = t
    session_state["playhead_playing"] = bool(evt.get("playing", False))

    try:
        sp = float(evt.get("speed", 1.0))
    except Exception:
        sp = 1.0
    if not (sp > 0):
        sp = 1.0
    session_state["playhead_speed"] = sp
    session_state["playhead_loop"] = bool(evt.get("loop", True))

    picked = evt.get("picked_event")
    if isinstance(picked, dict):
        session_state["playhead_picked_event"] = picked

    try:
        last = session_state.get("_playhead_last_logged")
        if not isinstance(last, dict):
            last = {}

        last_idx = last.get("idx")
        last_play = last.get("playing")
        last_ds = last.get("dataset_id")

        changed = (
            last_idx != idx
            or bool(last_play) != bool(session_state.get("playhead_playing"))
            or str(last_ds) != str(ds)
            or isinstance(picked, dict)
        )

        if changed:
            log_event_fn(
                "playhead_update",
                dataset_id=str(ds) if isinstance(ds, str) else None,
                idx=int(idx),
                t=float(t),
                playing=bool(session_state.get("playhead_playing")),
                speed=float(session_state.get("playhead_speed", 1.0)),
                loop=bool(session_state.get("playhead_loop", True)),
                picked_event=bool(isinstance(picked, dict)),
                proc=proc_metrics_fn(),
            )

        session_state["_playhead_last_logged"] = {
            "dataset_id": str(ds) if isinstance(ds, str) else None,
            "idx": int(idx),
            "playing": bool(session_state.get("playhead_playing")),
        }
    except Exception:
        pass


__all__ = [
    "consume_mech_pick_event",
    "consume_playhead_event",
    "consume_plotly_pick_events",
    "consume_svg_pick_event",
]
