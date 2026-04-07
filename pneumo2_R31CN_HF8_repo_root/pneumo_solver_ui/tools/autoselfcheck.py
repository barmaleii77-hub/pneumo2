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

Использование:
- UI: вызвать ensure_autoselfcheck_once() при старте (и показать в sidebar)
- Opt: вызвать ensure_autoselfcheck_once() перед первой оценкой
"""

from __future__ import annotations

import os
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
        if isinstance(rc, dict) and 'ok' in rc:
            ok = bool(rc.get('ok'))
        elif rc is None:
            ok = True
        elif isinstance(rc, bool):
            ok = bool(rc)
        else:
            try:
                ok = (int(rc) == 0)
            except Exception:
                # если вернули что-то экзотическое — считаем успехом
                ok = True

        return bool(ok), rc

    except SystemExit as e:
        code = int(getattr(e, 'code', 1) or 0)
        return code == 0, code
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def ensure_autoselfcheck_once(strict: Optional[bool] = None) -> AutoSelfcheckResult:
    """Выполняет быстрые автосамопроверки один раз на процесс."""
    global _LAST
    if _LAST is not None:
        return _LAST

    if str(os.environ.get('PNEUMO_AUTOCHECK_DISABLE', '0')).strip() == '1':
        _LAST = AutoSelfcheckResult(
            ok=True,
            elapsed_s=0.0,
            results={'disabled': True},
            details={'disabled': True},
            summary='autoselfcheck: disabled',
            messages=['disabled'],
        )
        return _LAST

    if strict is None:
        strict = str(os.environ.get('PNEUMO_AUTOCHECK_STRICT', '0')).strip() == '1'

    t0 = time.time()
    details: Dict[str, Any] = {}

    # Импорты делаем лениво и через file-loading,
    # чтобы работало и при запуске из zip/Windows.
    from pathlib import Path
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    # Чтобы model_* импортировались как package, добавляем parent директорию в sys.path
    if str(root.parent) not in sys.path:
        sys.path.insert(0, str(root.parent))

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore
        return mod

    param_contract_check = _load('param_contract_check', root / 'tools' / 'param_contract_check.py')
    mech_energy_smoke_check = _load('mech_energy_smoke_check', root / 'tools' / 'mech_energy_smoke_check.py')

    ok_all = True

    ok, rc = _run_step('param_contract_check', param_contract_check.main)
    details['param_contract_check'] = {'ok': ok, 'rc': rc}
    ok_all = ok_all and ok

    ok, rc = _run_step('mech_energy_smoke_check', lambda: mech_energy_smoke_check.main(argv=[]))
    details['mech_energy_smoke_check'] = {'ok': ok, 'rc': rc}
    ok_all = ok_all and ok

    # 3) compileall (syntax safety)
    if str(os.environ.get('PNEUMO_AUTOCHECK_NO_COMPILE', '0')).strip() != '1':
        def _compileall():
            import compileall
            ok_ = bool(compileall.compile_dir(str(root), quiet=1))
            return {'ok': ok_}

        ok, rc = _run_step('compileall', _compileall)
        details['compileall'] = {'ok': ok, 'rc': rc}
        ok_all = ok_all and ok
    else:
        details['compileall'] = {'skipped': True}


    # 3.5) UI layout guard (защита от отката к «широким таблицам»)
    def _ui_layout_guard() -> Dict[str, Any]:
        try:
            ui_path = root / 'pneumo_ui_app.py'
            txt = ui_path.read_text(encoding='utf-8', errors='ignore')
            issues = []
            if 'Новый редактор параметров: список + карточка' not in txt:
                issues.append('missing params marker')
            if 'Новый редактор тест-набора: список + карточка' not in txt:
                issues.append('missing suite marker')
            if 'df_params_edit = st.data_editor(' in txt:
                issues.append('old params data_editor still present')
            if 'df_suite_edit = st.data_editor(' in txt:
                issues.append('old suite data_editor still present')
            return {'ok': len(issues) == 0, 'issues': issues}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    ok, rc = _run_step('ui_layout_guard', _ui_layout_guard)
    details['ui_layout_guard'] = {'ok': ok, 'rc': rc}
    ok_all = ok_all and ok

    # 4) import smoke (минимальный)
    if str(os.environ.get('PNEUMO_AUTOCHECK_NO_IMPORT', '0')).strip() != '1':
        def _import_smoke():
            import importlib

            imported = []
            for mod_name in [
                'pneumo_solver_ui',
                'pneumo_solver_ui.model_pneumo_v9_mech_doublewishbone_worldroad',
            ]:
                m = importlib.import_module(mod_name)
                imported.append(mod_name)
                if mod_name.endswith('worldroad'):
                    missing = [
                        a for a in (
                            'mdot_orifice_smooth',
                            'mdot_orifice_signed_smooth',
                        ) if not hasattr(m, a)
                    ]
                    if missing:
                        return {'ok': False, 'imported': imported, 'missing': missing}

            return {'ok': True, 'imported': imported}

        ok, rc = _run_step('import_smoke', _import_smoke)
        details['import_smoke'] = {'ok': ok, 'rc': rc}
        ok_all = ok_all and ok
    else:
        details['import_smoke'] = {'skipped': True}

    elapsed = float(time.time() - t0)

    # UI-friendly fields
    failures = []
    messages = []
    try:
        for _name, _info in (details or {}).items():
            if isinstance(_info, dict) and (not bool(_info.get('ok', True))):
                failures.append({'step': _name, 'rc': _info.get('rc')})
                messages.append(f"{_name}: FAIL (rc={_info.get('rc')})")
    except Exception:
        failures = []
        messages = []

    if ok_all:
        summary = f"autoselfcheck: PASS ({elapsed:.2f}s)"
    else:
        bad = ', '.join([f.get('step', '?') for f in failures]) if failures else 'unknown'
        summary = f"autoselfcheck: FAIL ({len(failures)}) [{bad}] ({elapsed:.2f}s)"

    _LAST = AutoSelfcheckResult(
        ok=ok_all,
        elapsed_s=elapsed,
        results=details,
        failures=failures,
        summary=summary,
        messages=messages,
        details=details,
    )

    if strict and (not ok_all):
        raise RuntimeError(f'AutoSelfcheck FAIL: {details}')

    return _LAST


def format_summary(res: AutoSelfcheckResult) -> str:
    """Короткая строка для UI/логов."""
    if getattr(res, 'summary', ''):
        return str(res.summary)
    if res.details.get('disabled'):
        return 'autoselfcheck: disabled'
    return f"autoselfcheck: {'PASS' if res.ok else 'FAIL'} ({res.elapsed_s:.2f}s)"


def run_quick_autoselfcheck(strict: bool = False) -> Dict[str, Any]:
    """Совместимый с UI wrapper: возвращает dict (ok/messages/details)."""
    res = ensure_autoselfcheck_once(strict=strict)
    messages = []
    try:
        for name, info in (res.details or {}).items():
            if isinstance(info, dict) and not bool(info.get('ok', True)):
                messages.append(f"{name}: FAIL (rc={info.get('rc')})")
    except Exception:
        pass
    return {
        'ok': bool(res.ok),
        'elapsed_s': float(res.elapsed_s),
        'summary': getattr(res, 'summary', ''),
        'results': getattr(res, 'results', res.details),
        'failures': getattr(res, 'failures', []),
        'details': res.details,
        'messages': getattr(res, 'messages', messages),
    }
