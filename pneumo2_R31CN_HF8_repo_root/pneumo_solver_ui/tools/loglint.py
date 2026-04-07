#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""loglint.py

Валидатор JSONL-логов (один JSON на строку) для повышения надёжности диагностики.

Зачем это нужно
---------------
В инженерных проектах часто появляются ситуации: "логи есть, но их нельзя парсить":
- битые строки,
- не-JSON значения (NaN/Inf),
- отсутствие ключевых полей,
- разъехавшийся порядок событий.

Этот скрипт делает логи **самопроверяемыми**:
- проверяет парсимость каждой строки,
- проверяет минимальные/строгие инварианты записи (ts/event/...),
- (опционально) проверяет монотонность seq и парность span_start/span_end,
- генерирует отчёт JSON+MD,
- выдаёт ненулевой exit code при ошибках.

Использование
-------------
Проверить один файл:
  python pneumo_solver_ui/tools/loglint.py --path pneumo_solver_ui/logs/metrics_combined.jsonl --schema ui

Проверить папку рекурсивно:
  python pneumo_solver_ui/tools/loglint.py --path pneumo_solver_ui/logs --recursive --schema ui

Строгий режим (для CI/harness):
  python pneumo_solver_ui/tools/loglint.py --path ... --schema ui --strict --check_spans --check_seq

"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class LintError:
    file: str
    line: int
    kind: str
    message: str


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


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _validate_ts(ts: Any) -> bool:
    if not isinstance(ts, str) or not ts.strip():
        return False
    try:
        _ = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except Exception:
        return False




def _is_semver(s: Any) -> bool:
    """Проверка semver-подобной строки X.Y.Z (без строгих prerelease/build)."""
    try:
        if not isinstance(s, str) or not s.strip():
            return False
        import re as _re

        return bool(_re.match(r"^\d+\.\d+\.\d+$", s.strip()))
    except Exception:
        return False

def _schema_rules(name: str, strict: bool) -> Dict[str, Any]:
    """Мини-схемы (без зависимости от jsonschema).

    Полноценная JSON Schema поддержка добавлена как опция (если установлен jsonschema),
    но базовые инварианты проверяем всегда.

    strict=True:
      - добавляет требования к schema/schema_version/event_id/seq/trace_id
      - включает дополнительные проверки порядка (seq) и span (если включены флаги)
    """
    name = (name or "any").lower()

    if name == "ui":
        req = ["ts", "event", "release", "session_id", "pid"]
        types = {"ts": "str", "event": "str", "release": "str", "session_id": "str", "pid": "int"}
        if strict:
            req = req + ["schema", "schema_version", "event_id", "seq", "trace_id"]
            types.update({"schema": "str", "schema_version": "str", "event_id": "str", "seq": "int", "trace_id": "str"})
        return {"required": req, "types": types, "key_field": "session_id", "schema_value": "ui"}

    if name == "harness":
        req = ["ts", "event", "release", "run_id", "level"]
        types = {"ts": "str", "event": "str", "release": "str", "run_id": "str", "level": "str"}
        if strict:
            req = req + ["schema", "schema_version", "event_id", "seq", "trace_id"]
            types.update({"schema": "str", "schema_version": "str", "event_id": "str", "seq": "int", "trace_id": "str"})
        return {"required": req, "types": types, "key_field": "run_id", "schema_value": "harness"}

    # any
    req = ["ts", "event"]
    types = {"ts": "str", "event": "str"}
    if strict:
        # не заставляем любой лог иметь все поля, но если есть — проверяем типы
        types.update({"schema": "str", "schema_version": "str", "event_id": "str", "seq": "int", "trace_id": "str"})
    return {"required": req, "types": types, "key_field": None}


def _validate_record(rec: Any, schema: str, strict: bool) -> List[str]:
    errs: List[str] = []
    if not isinstance(rec, dict):
        return ["record is not an object/dict"]

    rules = _schema_rules(schema, strict)
    req = rules.get("required") or []
    types = rules.get("types") or {}

    for k in req:
        if k not in rec:
            errs.append(f"missing required field: {k}")

    # обязательные инварианты
    if "ts" in rec and not _validate_ts(rec.get("ts")):
        errs.append("field ts is not a valid timestamp string")

    if "event" in rec and not _is_nonempty_str(rec.get("event")):
        errs.append("field event is empty or not a string")

    # типы
    for k, t in types.items():
        if k not in rec:
            continue
        v = rec.get(k)
        if t == "str" and not isinstance(v, str):
            errs.append(f"field {k} expected str, got {type(v).__name__}")
        elif t == "int" and not isinstance(v, int):
            errs.append(f"field {k} expected int, got {type(v).__name__}")


    # строгие проверки контракта (не только типы)
    if strict:
        expected_schema = rules.get("schema_value")
        if expected_schema:
            if rec.get("schema") != expected_schema:
                errs.append(f"field schema expected const '{expected_schema}', got {rec.get('schema')!r}")

        if "schema_version" in rec and not _is_semver(rec.get("schema_version")):
            errs.append("field schema_version is not semver X.Y.Z")

        # ключевой идентификатор (session_id/run_id) должен быть непустым
        kf = rules.get("key_field")
        if kf and (kf in rec) and not _is_nonempty_str(rec.get(kf)):
            errs.append(f"field {kf} is empty or not a string")

        # seq должен быть положительным
        try:
            if "seq" in rec and isinstance(rec.get("seq"), int) and int(rec.get("seq")) < 1:
                errs.append("field seq must be >= 1")
        except Exception:
            pass

    return errs
def _try_jsonschema_validate(records: List[dict], schema_name: str, strict: bool) -> Optional[str]:
    """Optional строгая JSON Schema валидация.

    Возвращает строку с ошибкой, если jsonschema установлен и валидация не прошла.
    Если jsonschema отсутствует — возвращает None.
    """
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except Exception:
        return None

    schema_name_l = (schema_name or "any").lower()

    if schema_name_l == "ui":
        required = ["ts", "event", "release", "session_id", "pid"]
        props: Dict[str, Any] = {
            "ts": {"type": "string"},
            "event": {"type": "string"},
            "release": {"type": "string"},
            "session_id": {"type": "string"},
            "pid": {"type": "integer"},
        }
        if strict:
            required += ["schema", "schema_version", "event_id", "seq", "trace_id"]
            props.update(
                {
                    "schema": {"type": "string", "const": "ui"},
                    "schema_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                    "event_id": {"type": "string"},
                    "seq": {"type": "integer"},
                    "trace_id": {"type": "string"},
                }
            )
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": required,
            "properties": props,
            "additionalProperties": True,
        }
    elif schema_name_l == "harness":
        required = ["ts", "event", "release", "run_id", "level"]
        props = {
            "ts": {"type": "string"},
            "event": {"type": "string"},
            "release": {"type": "string"},
            "run_id": {"type": "string"},
            "level": {"type": "string"},
        }
        if strict:
            required += ["schema", "schema_version", "event_id", "seq", "trace_id"]
            props.update(
                {
                    "schema": {"type": "string", "const": "harness"},
                    "schema_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                    "event_id": {"type": "string"},
                    "seq": {"type": "integer"},
                    "trace_id": {"type": "string"},
                }
            )
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": required,
            "properties": props,
            "additionalProperties": True,
        }
    else:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["ts", "event"],
            "properties": {"ts": {"type": "string"}, "event": {"type": "string"}},
            "additionalProperties": True,
        }

    v = Draft202012Validator(schema)
    for i, r in enumerate(records, 1):
        err = next(iter(v.iter_errors(r)), None)
        if err is not None:
            return f"jsonschema violation at record #{i}: {err.message}"
    return None


def lint_file(
    path: Path,
    schema: str,
    strict: bool = False,
    check_seq: bool = False,
    check_spans: bool = False,
    max_errors: int = 50,
    max_records_for_jsonschema: int = 2000,
) -> Tuple[int, List[LintError]]:
    errors: List[LintError] = []
    n_lines = 0

    rules = _schema_rules(schema, strict)
    key_field = rules.get("key_field")

    # stream checks (без чтения всего файла в память)
    last_seq: Dict[str, int] = {}
    open_spans: Dict[str, Tuple[int, Dict[str, Any]]] = {}  # span_id -> (line, rec)

    # Для jsonschema-валидации держим ограниченное число записей
    recs_for_jsonschema: List[dict] = []

    def _push_error(line: int, kind: str, message: str) -> None:
        errors.append(LintError(str(path), int(line), str(kind), str(message)))

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                line = line.strip("\n")
                if not line.strip():
                    continue
                n_lines += 1

                try:
                    rec = json.loads(line)
                except Exception as e:
                    _push_error(i, "json_parse", f"cannot parse JSON: {e}")
                    if len(errors) >= max_errors:
                        break
                    continue

                if isinstance(rec, dict) and len(recs_for_jsonschema) < max_records_for_jsonschema:
                    recs_for_jsonschema.append(rec)

                # базовые/строгие правила
                for msg in _validate_record(rec, schema, strict):
                    _push_error(i, "schema", msg)
                    if len(errors) >= max_errors:
                        break
                if len(errors) >= max_errors:
                    break

                if not isinstance(rec, dict):
                    continue

                # check_seq
                if check_seq:
                    k_base = None
                    if key_field and isinstance(rec.get(key_field), str):
                        k_base = rec.get(key_field)
                    elif key_field:
                        k_base = "<missing>"
                    else:
                        k_base = "<global>"

                    pid = rec.get("pid")
                    if not isinstance(pid, int):
                        extra_reserved = rec.get("_extra_reserved")
                        if isinstance(extra_reserved, dict) and isinstance(extra_reserved.get("pid"), int):
                            pid = int(extra_reserved.get("pid"))
                    k = f"{k_base}|pid={pid}" if isinstance(pid, int) else k_base

                    seq = rec.get("seq")
                    if strict and seq is None:
                        _push_error(i, "seq", "missing seq in strict mode")
                    elif seq is not None and not isinstance(seq, int):
                        _push_error(i, "seq", f"seq expected int, got {type(seq).__name__}")
                    elif isinstance(seq, int):
                        prev = last_seq.get(k)
                        if prev is not None and seq <= prev:
                            _push_error(i, "seq", f"non-monotonic seq: {seq} <= {prev} (key={k})")
                        last_seq[k] = seq

                # check_spans
                if check_spans:
                    ev = rec.get("event")
                    if ev in ("span_start", "span_end"):
                        span_id = rec.get("span_id")
                        span_name = rec.get("span_name")
                        if strict and (not _is_nonempty_str(span_id) or not _is_nonempty_str(span_name)):
                            _push_error(i, "span", "span_start/span_end require span_id and span_name in strict mode")
                            continue
                        if not _is_nonempty_str(span_id):
                            # в нестрогом режиме просто пропускаем
                            continue

                        sid = str(span_id)

                        if ev == "span_start":
                            if sid in open_spans:
                                _push_error(i, "span", f"duplicate span_start for span_id={sid}")
                            else:
                                open_spans[sid] = (i, rec)
                        else:  # span_end
                            if sid not in open_spans:
                                _push_error(i, "span", f"span_end without span_start for span_id={sid}")
                            else:
                                start_line, start_rec = open_spans.pop(sid)
                                # best-effort checks
                                try:
                                    if _is_nonempty_str(span_name) and _is_nonempty_str(start_rec.get("span_name")):
                                        if str(span_name) != str(start_rec.get("span_name")):
                                            _push_error(i, "span", f"span_name mismatch for span_id={sid}: start={start_rec.get('span_name')} end={span_name}")
                                except Exception:
                                    pass
                                try:
                                    dm = rec.get("duration_ms")
                                    if dm is not None:
                                        if not isinstance(dm, (int, float)):
                                            _push_error(i, "span", f"duration_ms expected number, got {type(dm).__name__}")
                                        else:
                                            if not math.isfinite(float(dm)) or float(dm) < 0:
                                                _push_error(i, "span", f"duration_ms invalid: {dm}")
                                except Exception:
                                    pass

                if len(errors) >= max_errors:
                    break

    except Exception as e:
        _push_error(0, "io", f"cannot read file: {e}")

    # jsonschema check (optional)
    try:
        msg = _try_jsonschema_validate(recs_for_jsonschema, schema, strict)
        if msg:
            _push_error(0, "jsonschema", msg)
    except Exception as e:
        _push_error(0, "jsonschema", f"jsonschema validate failed: {e}")

    # unmatched spans
    if check_spans and open_spans:
        for sid, (line0, start_rec) in list(open_spans.items())[: max(1, max_errors - len(errors))]:
            _push_error(line0, "span", f"span_start without span_end for span_id={sid}")

    return int(n_lines), errors


def lint_path(
    path: Path,
    schema: str,
    recursive: bool,
    strict: bool,
    check_seq: bool,
    check_spans: bool,
    max_errors: int,
) -> Tuple[Dict[str, Any], int]:
    files = _iter_jsonl_files(path, recursive=recursive)
    report: Dict[str, Any] = {
        "generated_at": _now_iso(),
        "schema": schema,
        "strict": bool(strict),
        "check_seq": bool(check_seq),
        "check_spans": bool(check_spans),
        "files_checked": int(len(files)),
        "total_records": 0,
        "total_errors": 0,
        "per_file": {},
        "errors": [],
    }
    rc = 0
    for fp in files:
        n, errs = lint_file(
            fp,
            schema=schema,
            strict=strict,
            check_seq=check_seq,
            check_spans=check_spans,
            max_errors=max_errors,
        )
        report["total_records"] += int(n)
        report["total_errors"] += int(len(errs))
        report["per_file"][str(fp)] = {"records": int(n), "errors": int(len(errs))}
        for e in errs:
            report["errors"].append({"file": e.file, "line": e.line, "kind": e.kind, "message": e.message})
        if errs:
            rc = 2
    return report, rc


def write_report(out_dir: Path, report: Dict[str, Any]) -> Tuple[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / "loglint_report.json"
    mp = out_dir / "loglint_report.md"

    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # md
    lines: List[str] = []
    lines.append(f"# LOGLINT report")
    lines.append("")
    lines.append(f"Generated at: `{report.get('generated_at')}`")
    lines.append(f"Schema: `{report.get('schema')}`")
    lines.append(f"Strict: `{report.get('strict')}`")
    lines.append(f"check_seq: `{report.get('check_seq')}`")
    lines.append(f"check_spans: `{report.get('check_spans')}`")
    lines.append("")
    lines.append(f"Files checked: **{report.get('files_checked')}**")
    lines.append(f"Total records: **{report.get('total_records')}**")
    lines.append(f"Total errors: **{report.get('total_errors')}**")
    lines.append("")
    if report.get("total_errors", 0):
        lines.append("## Errors (first 50)")
        lines.append("")
        for e in (report.get("errors") or [])[:50]:
            lines.append(f"- `{e.get('file')}`:{e.get('line')} **{e.get('kind')}** — {e.get('message')}")
    else:
        lines.append("✅ No errors.")

    mp.write_text("\n".join(lines), encoding="utf-8")
    return str(jp), str(mp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="file or directory to lint")
    ap.add_argument("--recursive", action="store_true", help="if path is directory, scan recursively")
    ap.add_argument("--schema", default="any", help="ui|harness|any")
    ap.add_argument("--out_dir", default=".", help="where to write report files")
    ap.add_argument("--max_errors", type=int, default=50)

    ap.add_argument("--strict", action="store_true", help="enable strict mode (more required fields)")
    ap.add_argument("--check_seq", action="store_true", help="validate monotonic seq (recommended for CI)")
    ap.add_argument("--check_spans", action="store_true", help="validate span_start/span_end pairing")

    args = ap.parse_args()

    path = Path(args.path)
    out_dir = Path(args.out_dir)

    # defaults: в strict режиме включаем доп. проверки автоматически
    strict = bool(args.strict)
    check_seq = bool(args.check_seq or strict)
    check_spans = bool(args.check_spans or strict)

    report, rc = lint_path(
        path=path,
        schema=args.schema,
        recursive=bool(args.recursive),
        strict=strict,
        check_seq=check_seq,
        check_spans=check_spans,
        max_errors=int(args.max_errors),
    )
    jp, mp = write_report(out_dir, report)

    print("=== LOGLINT ===")
    print(f"Path: {path}")
    print(f"Schema: {args.schema}")
    print(f"Strict: {strict}")
    print(f"check_seq: {check_seq}")
    print(f"check_spans: {check_spans}")
    print(f"Files: {report['files_checked']}")
    print(f"Records: {report['total_records']}")
    print(f"Errors: {report['total_errors']}")
    print(f"Report JSON: {jp}")
    print(f"Report MD:   {mp}")

    return 0 if int(report["total_errors"]) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
