#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_requirements_from_context.py

Goal
----
Generate a *traceable* requirements list from the project context artifacts
(chat exports / MHTML notes) and write them into docs as:

- docs/01_RequirementsFromContext_RAW.md   (verbatim-ish, auto extracted)
- docs/01_RequirementsFromContext.json     (machine-readable)

This script is intentionally conservative: it extracts *candidate* requirement
statements using keyword heuristics. It is NOT a replacement for a curated
requirements document.

Usage
-----
python -m pneumo_solver_ui.tools.extract_requirements_from_context

You can also pass a custom context directory:
python -m pneumo_solver_ui.tools.extract_requirements_from_context --context-dir docs/context

Notes
-----
- We keep line numbers for traceability.
- For MHTML/HTML we do a simple tag strip (fast, no heavy deps).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Dict, Any


TRIGGER_RE = re.compile(
    r"\b(надо|нужно|должн\w*|треб\w*|важно|обяз\w*|хочу|сдела(й|ть)|добав\w*|убер\w*|исправ\w*|проверь|нельзя)\b",
    re.IGNORECASE,
)

DOMAIN_RE = re.compile(
    r"\b(UI|интерфейс|анимац\w*|график\w*|лог\w*|диагност\w*|калибров\w*|autopilot|автопилот\w*|baseline|бэйслайн\w*|детальн\w*|полный\s+лог|solv\w*|солвер\w*|оптимиз\w*|one\s*click|батник|скрипт|streamlit|plotly|npz|csv)\b",
    re.IGNORECASE,
)


@dataclass
class RequirementHit:
    rid: str
    source_file: str
    line_start: int
    line_end: int
    text: str
    category: str


def _strip_html(s: str) -> str:
    # quick & dirty removal of tags + collapse spaces
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _guess_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["анимац", "3d", "2d", "play", "ползунк", "кадр", "frame"]):
        return "animation"
    if any(k in t for k in ["интерфейс", "ui", "кноп", "чекбокс", "вклад", "страниц", "график", "plot", "matplotlib", "plotly"]):
        return "ui"
    if any(k in t for k in ["лог", "npz", "csv", "диагност", "zip", "ошиб", "traceback"]):
        return "logging_diagnostics"
    if any(k in t for k in ["калибров", "calib"]):
        return "calibration"
    if any(k in t for k in ["автопилот", "autopilot", "оптимиз", "optimizer", "botorch", "bayes"]):
        return "optimization_autopilot"
    if any(k in t for k in ["солвер", "solver", "модель", "матмодел", "физик", "крен", "тангаж", "дифферент", "колес", "шина"]):
        return "physics_model"
    return "other"


def _normalize_for_dedupe(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^0-9a-zа-я_\- ]+", "", s)
    return s


def _iter_context_files(context_dir: Path) -> Iterable[Path]:
    exts = {".txt", ".mhtml", ".html", ".md"}
    for p in sorted(context_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _extract_from_text(lines: List[str], source_name: str) -> List[RequirementHit]:
    hits: List[RequirementHit] = []
    seen: set[str] = set()

    for i, raw in enumerate(lines):
        line_no = i + 1
        line = raw.strip()
        if not line:
            continue

        if len(line) < 12:
            continue

        # candidate if trigger present; domain keyword increases score.
        if not TRIGGER_RE.search(line):
            continue

        # reject very long html dumps
        if len(line) > 400:
            continue

        score = 1
        if DOMAIN_RE.search(line):
            score += 2
        if line.startswith(("- ", "•", "* ")):
            score += 1

        if score < 1:
            continue

        norm = _normalize_for_dedupe(line)
        if norm in seen:
            continue
        seen.add(norm)

        rid = f"REQ-{abs(hash((source_name, line_no, norm))) % 10**8:08d}"
        hits.append(
            RequirementHit(
                rid=rid,
                source_file=source_name,
                line_start=line_no,
                line_end=line_no,
                text=line,
                category=_guess_category(line),
            )
        )

    return hits


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-dir", default="docs/context", help="Folder with context artifacts")
    ap.add_argument("--out-md", default="docs/01_RequirementsFromContext_RAW.md")
    ap.add_argument("--out-json", default="docs/01_RequirementsFromContext.json")
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    context_dir = (repo_root / args.context_dir).resolve()
    out_md = (repo_root / args.out_md).resolve()
    out_json = (repo_root / args.out_json).resolve()

    if not context_dir.exists():
        raise SystemExit(f"Context dir not found: {context_dir}")

    all_hits: List[RequirementHit] = []

    for fp in _iter_context_files(context_dir):
        source_name = fp.name
        data = fp.read_text(encoding="utf-8", errors="ignore")
        if fp.suffix.lower() in {".mhtml", ".html"}:
            data = _strip_html(data)
            # after strip we have a single line; split on sentence-ish boundaries
            # to create pseudo-lines with traceability to file-level (line numbers lost).
            # We'll still emit line_start=1.
            pseudo_lines = re.split(r"(?<=[\.!\?])\s+", data)
            # keep some chunking for long docs
            lines = [s.strip() for s in pseudo_lines if s.strip()]
        else:
            lines = data.splitlines()

        hits = _extract_from_text(lines, source_name)
        all_hits.extend(hits)

    # stable sort by category then file then line
    all_hits.sort(key=lambda h: (h.category, h.source_file, h.line_start, h.rid))

    # write json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps([asdict(h) for h in all_hits], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # write md
    by_cat: Dict[str, List[RequirementHit]] = {}
    for h in all_hits:
        by_cat.setdefault(h.category, []).append(h)

    md_lines: List[str] = []
    md_lines.append("# Requirements from context (RAW, auto-extracted)\n")
    md_lines.append("> Этот файл генерируется скриптом `tools/extract_requirements_from_context.py`.\n")
    md_lines.append("> Это *черновик*: тут есть шум, повторы и не всё является строгими требованиями.\n")
    md_lines.append(f"\nВсего строк-кандидатов: **{len(all_hits)}**\n")

    for cat in sorted(by_cat.keys()):
        md_lines.append(f"\n## {cat}\n")
        for h in by_cat[cat]:
            md_lines.append(
                f"- **{h.rid}** ({h.source_file}:{h.line_start}) — {h.text}"
            )

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_json}")
    print(f"Hits: {len(all_hits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
