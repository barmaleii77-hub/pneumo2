from __future__ import annotations

from typing import Any, Callable, Mapping

import pandas as pd


PACKAGING_METRIC_SPECS = (
    {
        "metric_key": "мин_зазор_пружина_цилиндр_м",
        "target_key": "мин_зазор_пружина_цилиндр_м",
        "param_key": "autoverif_spring_host_min_clearance_m",
        "label": "Пружина↔цилиндр",
        "sense": "min",
    },
    {
        "metric_key": "мин_зазор_пружина_пружина_м",
        "target_key": "мин_зазор_пружина_пружина_м",
        "param_key": "autoverif_spring_pair_min_clearance_m",
        "label": "Пружина↔пружина",
        "sense": "min",
    },
    {
        "metric_key": "мин_зазор_пружина_до_крышки_м",
        "target_key": "",
        "param_key": "autoverif_spring_cap_min_margin_m",
        "label": "Пружина↔крышка",
        "sense": "min",
    },
    {
        "metric_key": "макс_ошибка_midstroke_t0_м",
        "target_key": "макс_ошибка_midstroke_t0_м",
        "param_key": "autoverif_midstroke_t0_max_error_m",
        "label": "Midstroke t0",
        "sense": "max",
    },
    {
        "metric_key": "мин_запас_до_coil_bind_пружины_м",
        "target_key": "мин_запас_до_coil_bind_пружины_м",
        "param_key": "autoverif_coilbind_min_margin_m",
        "label": "Coil-bind",
        "sense": "min",
    },
)

PACKAGING_AUTOVERIF_FLAGS = (
    ("packaging_metrics_fail", "Сбор packaging metrics"),
    ("packaging_metrics_bad", "Сбор packaging metrics"),
    ("spring_host_clearance", "Пружина↔цилиндр"),
    ("spring_pair_clearance", "Пружина↔пружина"),
    ("spring_cap_gap", "Пружина↔крышка"),
    ("midstroke_t0", "Midstroke t0"),
    ("coil_bind_risk", "Coil-bind"),
)


def _finite_float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _format_threshold(sense: str, value: float | None, fmt_func: Callable[[Any, int], str]) -> str:
    if value is None:
        return "—"
    sign = ">=" if sense == "min" else "<="
    return f"{sign} {fmt_func(value, 4)}"


def _status_line(ok: bool, failures: list[str], unknowns: list[str] | None = None) -> str:
    if ok:
        if unknowns:
            return "OK (частично без данных)"
        return "OK"
    text = "FAIL: " + ", ".join(failures)
    if unknowns:
        text += " | без данных: " + ", ".join(unknowns)
    return text


def collect_packaging_surface_metrics(
    metrics: Mapping[str, Any] | None,
    *,
    targets: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metrics_dict = dict(metrics or {})
    targets_dict = dict(targets or {})
    params_dict = dict(params or {})
    verif_flags = {
        str(flag).strip()
        for flag in str(metrics_dict.get("верификация_флаги", "") or "").split(";")
        if str(flag).strip()
    }

    target_failures: list[str] = []
    target_unknowns: list[str] = []
    for spec in PACKAGING_METRIC_SPECS:
        target_key = str(spec["target_key"] or "").strip()
        if not target_key or target_key not in targets_dict:
            continue
        target_value = _finite_float_or_none(targets_dict.get(target_key))
        if target_value is None:
            continue
        metric_value = _finite_float_or_none(metrics_dict.get(spec["metric_key"]))
        if metric_value is None:
            target_unknowns.append(str(spec["label"]))
            continue
        sense = str(spec["sense"])
        fail = metric_value < target_value if sense == "min" else metric_value > target_value
        if fail:
            target_failures.append(str(spec["label"]))

    verif_failures = [label for flag, label in PACKAGING_AUTOVERIF_FLAGS if flag in verif_flags]
    packaging_metrics_ok = _finite_float_or_none(metrics_dict.get("anim_export_packaging_metrics_ok"))

    out = {
        "packaging_статус": str(metrics_dict.get("anim_export_packaging_status") or ""),
        "packaging_truth_ready": int(bool(metrics_dict.get("anim_export_packaging_truth_ready"))),
        "packaging_metrics_ok": (
            int(packaging_metrics_ok != 0.0)
            if packaging_metrics_ok is not None
            else None
        ),
        "packaging_цели_нарушения": ";".join(target_failures),
        "packaging_цели_неоценено": ";".join(target_unknowns),
        "packaging_верификация_нарушения": ";".join(verif_failures),
        "pass_packaging_цели": int(not target_failures),
        "pass_packaging_верификация": int(not verif_failures),
        "pass_packaging": int((not target_failures) and (not verif_failures)),
    }
    out["packaging_цели_статус"] = _status_line(
        ok=bool(out["pass_packaging_цели"]),
        failures=target_failures,
        unknowns=target_unknowns,
    )
    out["packaging_верификация_статус"] = _status_line(
        ok=bool(out["pass_packaging_верификация"]),
        failures=verif_failures,
    )
    return out


def packaging_error_surface_metrics(error_label: str = "test_error") -> dict[str, Any]:
    reason = str(error_label or "test_error")
    return {
        "packaging_статус": "error",
        "packaging_truth_ready": 0,
        "packaging_metrics_ok": 0,
        "packaging_цели_нарушения": reason,
        "packaging_цели_неоценено": "",
        "packaging_верификация_нарушения": reason,
        "packaging_цели_статус": f"FAIL: {reason}",
        "packaging_верификация_статус": f"FAIL: {reason}",
        "pass_packaging_цели": 0,
        "pass_packaging_верификация": 0,
        "pass_packaging": 0,
    }


def format_packaging_markdown_lines(
    metrics: Mapping[str, Any] | None,
    *,
    targets: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
    fmt_func: Callable[[Any, int], str] | None = None,
) -> list[str]:
    fmt_local = fmt_func or (lambda x, nd=4: str(x))
    metrics_dict = dict(metrics or {})
    targets_dict = dict(targets or {})
    params_dict = dict(params or {})
    summary = collect_packaging_surface_metrics(metrics_dict, targets=targets_dict, params=params_dict)

    status = str(summary.get("packaging_статус") or "n/a")
    truth_ready = "yes" if int(summary.get("packaging_truth_ready", 0)) == 1 else "no"
    metrics_ok = summary.get("packaging_metrics_ok")
    metrics_ok_text = "yes" if metrics_ok == 1 else ("no" if metrics_ok == 0 else "n/a")

    lines = [
        f"- exporter packaging: `{status}`, truth_ready={truth_ready}, metrics_ok={metrics_ok_text}\n",
        f"- packaging цели: **{'PASS' if int(summary.get('pass_packaging_цели', 0)) == 1 else 'FAIL'}**; {summary.get('packaging_цели_статус', '')}\n",
        f"- packaging autoverif: **{'PASS' if int(summary.get('pass_packaging_верификация', 0)) == 1 else 'FAIL'}**; {summary.get('packaging_верификация_статус', '')}\n",
    ]

    for spec in PACKAGING_METRIC_SPECS:
        metric_value = _finite_float_or_none(metrics_dict.get(spec["metric_key"]))
        target_value = _finite_float_or_none(targets_dict.get(spec["target_key"])) if spec["target_key"] else None
        param_value = _finite_float_or_none(params_dict.get(spec["param_key"])) if spec["param_key"] else None
        if metric_value is None and target_value is None and param_value is None:
            continue
        metric_text = fmt_local(metric_value, 4) if metric_value is not None else "n/a"
        target_text = _format_threshold(str(spec["sense"]), target_value, fmt_local)
        autoverif_text = _format_threshold(str(spec["sense"]), param_value, fmt_local)
        lines.append(
            f"- {spec['label']}: {metric_text} м; цель {target_text}; autoverif {autoverif_text}\n"
        )

    host_hits = _finite_float_or_none(metrics_dict.get("число_пересечений_пружина_цилиндр"))
    pair_hits = _finite_float_or_none(metrics_dict.get("число_пересечений_пружина_пружина"))
    fallback_count = _finite_float_or_none(metrics_dict.get("число_runtime_fallback_пружины"))
    if host_hits is not None or pair_hits is not None or fallback_count is not None:
        host_text = str(int(host_hits)) if host_hits is not None else "n/a"
        pair_text = str(int(pair_hits)) if pair_hits is not None else "n/a"
        fallback_text = str(int(fallback_count)) if fallback_count is not None else "n/a"
        lines.append(
            f"- интерференции: spring↔cylinder={host_text}, spring↔spring={pair_text}, runtime_fallback_families={fallback_text}\n"
        )

    return lines


def enrich_packaging_surface_df(
    df: pd.DataFrame | None,
    *,
    params: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    records = df.to_dict(orient="records")
    extras = [collect_packaging_surface_metrics(row, params=params) for row in records]
    extra_df = pd.DataFrame(extras, index=df.index)

    out = df.copy()
    for col in extra_df.columns:
        out[col] = extra_df[col]
    return out


__all__ = [
    "PACKAGING_AUTOVERIF_FLAGS",
    "PACKAGING_METRIC_SPECS",
    "collect_packaging_surface_metrics",
    "enrich_packaging_surface_df",
    "format_packaging_markdown_lines",
    "packaging_error_surface_metrics",
]
