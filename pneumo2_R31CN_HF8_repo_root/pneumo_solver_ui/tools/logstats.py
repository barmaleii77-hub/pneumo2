#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""logstats.py

Мини-инструмент для агрегирования JSONL-логов (ui/harness) в читаемый отчёт.

Цель:
- быстро понять "что происходило" (топ событий),
- увидеть частые ошибки,
- получить статистику по span_end (duration_ms) по span_name.

Использование:
  python pneumo_solver_ui/tools/logstats.py --path pneumo_solver_ui/logs --recursive --out_dir out

"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _iter_jsonl_files(path: Path, recursive: bool) -> List[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    if recursive:
        return sorted([p for p in path.rglob("*.jsonl") if p.is_file()])
    return sorted([p for p in path.glob("*.jsonl") if p.is_file()])


@dataclass
class SpanAgg:
    n: int = 0
    sum_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    samples: List[float] = None  # type: ignore

    def __post_init__(self):
        if self.samples is None:
            self.samples = []

    def add(self, x: float) -> None:
        self.n += 1
        self.sum_ms += float(x)
        self.min_ms = min(self.min_ms, float(x))
        self.max_ms = max(self.max_ms, float(x))
        # ограничиваем память (квантили approx)
        if len(self.samples) < 20000:
            self.samples.append(float(x))

    def mean(self) -> float:
        return float(self.sum_ms / self.n) if self.n else 0.0

    def q(self, q: float) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        k = int(round((len(s) - 1) * float(q)))
        k = max(0, min(len(s) - 1, k))
        return float(s[k])


def analyze(path: Path, recursive: bool = False) -> Dict[str, Any]:
    files = _iter_jsonl_files(path, recursive=recursive)

    ev_counter: Counter[str] = Counter()
    err_counter: Counter[str] = Counter()
    files_info: Dict[str, Any] = {}
    spans: Dict[str, SpanAgg] = defaultdict(SpanAgg)

    total_records = 0
    total_parse_errors = 0

    for fp in files:
        n = 0
        parse_err = 0
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n += 1
                total_records += 1
                try:
                    rec = json.loads(line)
                except Exception:
                    parse_err += 1
                    total_parse_errors += 1
                    continue
                if isinstance(rec, dict):
                    ev = rec.get("event")
                    if isinstance(ev, str):
                        ev_counter[ev] += 1
                        if "error" in ev.lower() or "exception" in ev.lower():
                            err_counter[ev] += 1

                    # span_end duration
                    if rec.get("event") == "span_end":
                        name = rec.get("span_name")
                        dm = rec.get("duration_ms")
                        if isinstance(name, str) and isinstance(dm, (int, float)):
                            if math.isfinite(float(dm)) and float(dm) >= 0:
                                spans[name].add(float(dm))

        files_info[str(fp)] = {"records": int(n), "parse_errors": int(parse_err)}

    span_summary = {}
    for name, agg in spans.items():
        span_summary[name] = {
            "n": agg.n,
            "mean_ms": round(agg.mean(), 3),
            "min_ms": round(float(agg.min_ms if agg.min_ms != float('inf') else 0.0), 3),
            "p50_ms": round(agg.q(0.50), 3),
            "p95_ms": round(agg.q(0.95), 3),
            "max_ms": round(agg.max_ms, 3),
        }

    out: Dict[str, Any] = {
        "generated_at": _now_iso(),
        "path": str(path),
        "recursive": bool(recursive),
        "files": int(len(files)),
        "total_records": int(total_records),
        "total_parse_errors": int(total_parse_errors),
        "top_events": ev_counter.most_common(50),
        "top_error_like_events": err_counter.most_common(50),
        "spans": span_summary,
        "per_file": files_info,
    }
    return out


def write_report(out_dir: Path, report: Dict[str, Any]) -> Tuple[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / "logstats.json"
    mp = out_dir / "logstats.md"

    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: List[str] = []
    lines.append("# LOGSTATS report")
    lines.append("")
    lines.append(f"Generated at: `{report.get('generated_at')}`")
    lines.append(f"Path: `{report.get('path')}`")
    lines.append(f"Recursive: `{report.get('recursive')}`")
    lines.append("")
    lines.append(f"Files: **{report.get('files')}**")
    lines.append(f"Total records: **{report.get('total_records')}**")
    lines.append(f"Total parse errors: **{report.get('total_parse_errors')}**")
    lines.append("")
    lines.append("## Top events")
    lines.append("")
    for ev, n in (report.get("top_events") or [])[:20]:
        lines.append(f"- `{ev}`: **{n}**")

    err_like = report.get("top_error_like_events") or []
    if err_like:
        lines.append("")
        lines.append("## Error-like events")
        lines.append("")
        for ev, n in err_like[:20]:
            lines.append(f"- `{ev}`: **{n}**")

    spans = report.get("spans") or {}
    if spans:
        lines.append("")
        lines.append("## Spans (duration_ms)")
        lines.append("")
        # sort by mean desc
        items = sorted(spans.items(), key=lambda kv: float(kv[1].get("mean_ms", 0.0)), reverse=True)
        for name, s in items[:30]:
            lines.append(
                f"- `{name}`: n={s.get('n')} mean={s.get('mean_ms')}ms p50={s.get('p50_ms')}ms p95={s.get('p95_ms')}ms max={s.get('max_ms')}ms"
            )

    mp.write_text("\n".join(lines), encoding="utf-8")
    return str(jp), str(mp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--out_dir", default=".")
    args = ap.parse_args()

    p = Path(args.path)
    rep = analyze(p, recursive=bool(args.recursive))
    jp, mp = write_report(Path(args.out_dir), rep)

    print("=== LOGSTATS ===")
    print(f"Path: {p}")
    print(f"Files: {rep.get('files')}")
    print(f"Records: {rep.get('total_records')}")
    print(f"Parse errors: {rep.get('total_parse_errors')}")
    print(f"Report JSON: {jp}")
    print(f"Report MD:   {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
