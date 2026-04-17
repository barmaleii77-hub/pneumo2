# -*- coding: utf-8 -*-
"""Автономные автосамопроверки (быстро) перед симуляцией/оптимизацией.

Задача:
- гарантировать, что базовая математика/контракты не сломаны,
  даже если пользователь запускает UI/оптимизатор без ручного preflight.

Принципы:
- быстрые проверки (обычно <1-3 сек на типичном ПК);
- запускается один раз на процесс (кешируется);
- не должна ломать запуск по умолчанию, но умеет работать в строгом режиме.

Что проверяем (quick):
1) contracts: tools/param_contract_check.py
2) механо‑энергоаудит (smoke): tools/mech_energy_smoke_check.py
3) compileall: компиляция всех *.py (syntax safety, без исполнения)
4) import smoke: импорт ключевых модулей (минимальный)

Опциональные env:
- PNEUMO_AUTOCHECK_STRICT=1       -> падать при FAIL
- PNEUMO_AUTOCHECK_DISABLE=1      -> полностью отключить
- PNEUMO_AUTOCHECK_NO_COMPILE=1   -> пропустить compileall
- PNEUMO_AUTOCHECK_NO_IMPORT=1    -> пропустить import smoke

Оптимизация запуска:
- успешный/неуспешный результат кешируется на диске по fingerprint текущего
  дерева `pneumo_solver_ui`, чтобы свежий процесс UI не повторял тяжёлые
  smoke-проверки без реального изменения кода.

Использование:
- UI: вызвать ensure_autoselfcheck_once() при старте (и показать в sidebar)
- Opt: вызвать ensure_autoselfcheck_once() перед первой оценкой
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AutoSelfcheckResult:
    # Результат автоматических самопроверок.
    #
    # Поля `results/failures/summary/messages` нужны UI (Diagnostics).
    # Поле `details` сохраняем для обратной совместимости.
    ok: bool
    elapsed_s: float
    results: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)
    summary: str = ""
    messages: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


_LAST: Optional[AutoSelfcheckResult] = None
_CACHE_SCHEMA_VERSION = "autoselfcheck_v2"


def _run_step(name: str, fn) -> tuple[bool, Any]:
    """Запускает шаг самопроверки и возвращает (ok, rc/details).

    Поддерживаемые контракты возврата:
    - int (0=ok)
    - bool
    - dict с ключом 'ok'
    - None (трактуется как ok)
    """
    try:
        rc = fn()

        ok: Optional[bool] = None
        if isinstance(rc, dict) and "ok" in rc:
            ok = bool(rc.get("ok"))
        elif rc is None:
            ok = True
        elif isinstance(rc, bool):
            ok = bool(rc)
        else:
            try:
                ok = int(rc) == 0
            except Exception:
                ok = True

        return bool(ok), rc

    except SystemExit as e:
        code = int(getattr(e, "code", 1) or 0)
        return code == 0, code
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _autoselfcheck_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _autoselfcheck_workspace_dir(root: Optional[Path] = None) -> Path:
    root = Path(root) if root is not None else _autoselfcheck_root()
    raw = str(os.environ.get("PNEUMO_WORKSPACE_DIR", "") or "").strip()
    workspace = Path(raw).expanduser().resolve() if raw else (root / "workspace")
    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return workspace


def _autoselfcheck_cache_path(root: Optional[Path] = None) -> Path:
    cache_dir = _autoselfcheck_workspace_dir(root) / "ui_state"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return cache_dir / "autoselfcheck_v2.json"


def _autoselfcheck_cache_fingerprint(root: Optional[Path] = None) -> str:
    root = Path(root) if root is not None else _autoselfcheck_root()
    flags = {
        "disable": str(os.environ.get("PNEUMO_AUTOCHECK_DISABLE", "0") or "0").strip(),
        "no_compile": str(os.environ.get("PNEUMO_AUTOCHECK_NO_COMPILE", "0") or "0").strip(),
        "no_import": str(os.environ.get("PNEUMO_AUTOCHECK_NO_IMPORT", "0") or "0").strip(),
    }
    digest = hashlib.sha256()
    digest.update(_CACHE_SCHEMA_VERSION.encode("utf-8"))
    digest.update(str(root).encode("utf-8"))
    digest.update(str(sys.version_info[:3]).encode("utf-8"))
    digest.update(json.dumps(flags, sort_keys=True).encode("utf-8"))
    for path in sorted(root.rglob("*.py")):
        try:
            stat = path.stat()
        except OSError:
            continue
        rel = path.relative_to(root)
        digest.update(str(rel).replace("\\", "/").encode("utf-8"))
        digest.update(str(int(stat.st_size)).encode("utf-8"))
        digest.update(str(int(stat.st_mtime_ns)).encode("utf-8"))
    return digest.hexdigest()


def _result_to_cache_payload(result: AutoSelfcheckResult, *, fingerprint: str) -> Dict[str, Any]:
    return {
        "schema": _CACHE_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "ok": bool(result.ok),
        "elapsed_s": float(result.elapsed_s),
        "results": dict(result.results or {}),
        "failures": list(result.failures or []),
        "summary": str(result.summary or ""),
        "messages": list(result.messages or []),
        "details": dict(result.details or {}),
    }


def _result_from_cache_payload(payload: Dict[str, Any]) -> Optional[AutoSelfcheckResult]:
    try:
        return AutoSelfcheckResult(
            ok=bool(payload.get("ok", False)),
            elapsed_s=float(payload.get("elapsed_s", 0.0) or 0.0),
            results=dict(payload.get("results") or {}),
            failures=list(payload.get("failures") or []),
            summary=str(payload.get("summary") or ""),
            messages=list(payload.get("messages") or []),
            details=dict(payload.get("details") or {}),
        )
    except Exception:
        return None


def _load_cached_autoselfcheck_result(
    cache_path: Path,
    *,
    fingerprint: str,
) -> Optional[AutoSelfcheckResult]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("schema") or "") != _CACHE_SCHEMA_VERSION:
        return None
    if str(payload.get("fingerprint") or "") != fingerprint:
        return None
    return _result_from_cache_payload(payload)


def _write_cached_autoselfcheck_result(
    cache_path: Path,
    *,
    fingerprint: str,
    result: AutoSelfcheckResult,
) -> None:
    payload = _result_to_cache_payload(result, fingerprint=fingerprint)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        os.replace(tmp_path, cache_path)
    except Exception:
        pass


def _build_autoselfcheck_result(*, strict: bool) -> AutoSelfcheckResult:
    t0 = time.time()
    details: Dict[str, Any] = {}

    import importlib.util

    root = _autoselfcheck_root()
    if str(root.parent) not in sys.path:
        sys.path.insert(0, str(root.parent))

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore
        return mod

    param_contract_check = _load("param_contract_check", root / "tools" / "param_contract_check.py")
    mech_energy_smoke_check = _load("mech_energy_smoke_check", root / "tools" / "mech_energy_smoke_check.py")

    ok_all = True

    ok, rc = _run_step("param_contract_check", param_contract_check.main)
    details["param_contract_check"] = {"ok": ok, "rc": rc}
    ok_all = ok_all and ok

    ok, rc = _run_step("mech_energy_smoke_check", lambda: mech_energy_smoke_check.main(argv=[]))
    details["mech_energy_smoke_check"] = {"ok": ok, "rc": rc}
    ok_all = ok_all and ok

    if str(os.environ.get("PNEUMO_AUTOCHECK_NO_COMPILE", "0")).strip() != "1":
        def _compileall():
            import compileall

            ok_ = bool(compileall.compile_dir(str(root), quiet=1))
            return {"ok": ok_}

        ok, rc = _run_step("compileall", _compileall)
        details["compileall"] = {"ok": ok, "rc": rc}
        ok_all = ok_all and ok
    else:
        details["compileall"] = {"skipped": True}

    def _ui_layout_guard() -> Dict[str, Any]:
        try:
            ui_path = root / "pneumo_ui_app.py"
            txt = ui_path.read_text(encoding="utf-8", errors="ignore")
            issues = []
            if "Новый редактор параметров: список + карточка" not in txt:
                issues.append("missing params marker")
            if "Новый редактор тест-набора: список + карточка" not in txt:
                issues.append("missing suite marker")
            if "df_params_edit = st.data_editor(" in txt:
                issues.append("old params data_editor still present")
            if "df_suite_edit = st.data_editor(" in txt:
                issues.append("old suite data_editor still present")
            return {"ok": len(issues) == 0, "issues": issues}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    ok, rc = _run_step("ui_layout_guard", _ui_layout_guard)
    details["ui_layout_guard"] = {"ok": ok, "rc": rc}
    ok_all = ok_all and ok

    if str(os.environ.get("PNEUMO_AUTOCHECK_NO_IMPORT", "0")).strip() != "1":
        def _import_smoke():
            import importlib

            imported = []
            for mod_name in [
                "pneumo_solver_ui",
                "pneumo_solver_ui.model_pneumo_v9_mech_doublewishbone_worldroad",
            ]:
                m = importlib.import_module(mod_name)
                imported.append(mod_name)
                if mod_name.endswith("worldroad"):
                    missing = [
                        attr
                        for attr in (
                            "mdot_orifice_smooth",
                            "mdot_orifice_signed_smooth",
                        )
                        if not hasattr(m, attr)
                    ]
                    if missing:
                        return {"ok": False, "imported": imported, "missing": missing}
            return {"ok": True, "imported": imported}

        ok, rc = _run_step("import_smoke", _import_smoke)
        details["import_smoke"] = {"ok": ok, "rc": rc}
        ok_all = ok_all and ok
    else:
        details["import_smoke"] = {"skipped": True}

    elapsed = float(time.time() - t0)
    failures = []
    messages = []
    try:
        for name, info in (details or {}).items():
            if isinstance(info, dict) and (not bool(info.get("ok", True))):
                failures.append({"step": name, "rc": info.get("rc")})
                messages.append(f"{name}: FAIL (rc={info.get('rc')})")
    except Exception:
        failures = []
        messages = []

    if ok_all:
        summary = f"autoselfcheck: PASS ({elapsed:.2f}s)"
    else:
        bad = ", ".join([failure.get("step", "?") for failure in failures]) if failures else "unknown"
        summary = f"autoselfcheck: FAIL ({len(failures)}) [{bad}] ({elapsed:.2f}s)"

    result = AutoSelfcheckResult(
        ok=ok_all,
        elapsed_s=elapsed,
        results=details,
        failures=failures,
        summary=summary,
        messages=messages,
        details=details,
    )
    if strict and (not ok_all):
        raise RuntimeError(f"AutoSelfcheck FAIL: {details}")
    return result


def ensure_autoselfcheck_once(strict: Optional[bool] = None) -> AutoSelfcheckResult:
    """Выполняет быстрые автосамопроверки один раз на процесс."""
    global _LAST
    if _LAST is not None:
        return _LAST

    if str(os.environ.get("PNEUMO_AUTOCHECK_DISABLE", "0")).strip() == "1":
        _LAST = AutoSelfcheckResult(
            ok=True,
            elapsed_s=0.0,
            results={"disabled": True},
            details={"disabled": True},
            summary="autoselfcheck: disabled",
            messages=["disabled"],
        )
        return _LAST

    if strict is None:
        strict = str(os.environ.get("PNEUMO_AUTOCHECK_STRICT", "0")).strip() == "1"

    root = _autoselfcheck_root()
    cache_path = _autoselfcheck_cache_path(root)
    fingerprint = _autoselfcheck_cache_fingerprint(root)
    cached = _load_cached_autoselfcheck_result(cache_path, fingerprint=fingerprint)
    if cached is not None:
        _LAST = cached
        if strict and (not _LAST.ok):
            raise RuntimeError(f"AutoSelfcheck FAIL: {_LAST.details}")
        return _LAST

    _LAST = _build_autoselfcheck_result(strict=bool(strict))
    _write_cached_autoselfcheck_result(cache_path, fingerprint=fingerprint, result=_LAST)
    return _LAST


def format_summary(res: AutoSelfcheckResult) -> str:
    """Короткая строка для UI/логов."""
    if getattr(res, "summary", ""):
        return str(res.summary)
    if res.details.get("disabled"):
        return "autoselfcheck: disabled"
    return f"autoselfcheck: {'PASS' if res.ok else 'FAIL'} ({res.elapsed_s:.2f}s)"


def run_quick_autoselfcheck(strict: bool = False) -> Dict[str, Any]:
    """Совместимый с UI wrapper: возвращает dict (ok/messages/details)."""
    res = ensure_autoselfcheck_once(strict=strict)
    messages = []
    try:
        for name, info in (res.details or {}).items():
            if isinstance(info, dict) and not bool(info.get("ok", True)):
                messages.append(f"{name}: FAIL (rc={info.get('rc')})")
    except Exception:
        pass
    return {
        "ok": bool(res.ok),
        "elapsed_s": float(res.elapsed_s),
        "summary": getattr(res, "summary", ""),
        "results": getattr(res, "results", res.details),
        "failures": getattr(res, "failures", []),
        "details": res.details,
        "messages": getattr(res, "messages", messages),
    }
