# -*- coding: utf-8 -*-
"""Проверка контрактов параметров (типы/режимы/диапазоны).

Назначение:
- ловить ошибки вида «пустое/некорректное базовое значение» ещё до запуска симуляции
- валидировать строковые режимы (термодинамика/стенка/модель расхода и т.п.)
- проверить соответствие default_base.json и default_ranges.json

Запуск:
    python tools/param_contract_check.py
"""

from __future__ import annotations

import json

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Keys that are allowed to be None in base.json (meaning: auto / default).
ALLOW_NONE_KEYS = {"corner_stiffness_ref_x_m"}


ALLOWED_THERMO = {"isothermal", "adiabatic", "thermal"}
ALLOWED_CP_MODEL = {"constant", "nist_air"}
ALLOWED_PASSIVE_FLOW = {"orifice", "iso6358"}
ALLOWED_WALL_MODEL = {"fixed_ambient", "lumped"}
# стенка_форма в модели трактуется как sphere (по умолчанию) или cylinder (если startswith('cyl'))
ALLOWED_WALL_SHAPE = {"sphere", "cyl", "cylinder"}
ALLOWED_H_GW_MODE = {"constant", "flow_dependent", "flow_dependent_hA", "flow"}


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _is_bool(x: Any) -> bool:
    return isinstance(x, bool)


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and len(x.strip()) > 0


def check_base_and_ranges(base: Dict[str, Any], ranges: Dict[str, Any]) -> List[str]:
    errs: List[str] = []

    # 1) базовые значения не None
    for k, v in base.items():
        if v is None and k not in ALLOW_NONE_KEYS:
            errs.append(f"base: ключ '{k}' имеет None")

    # 2) ranges: правильная форма [min,max]
    for k, rr in ranges.items():
        if not (isinstance(rr, (list, tuple)) and len(rr) == 2):
            errs.append(f"ranges: ключ '{k}' должен быть [min,max], сейчас {type(rr)} {rr}")
            continue
        lo, hi = rr
        if not _is_num(lo) or not _is_num(hi):
            errs.append(f"ranges: ключ '{k}' min/max должны быть числами, сейчас lo={lo}, hi={hi}")
            continue
        if float(lo) > float(hi):
            errs.append(f"ranges: ключ '{k}' имеет lo>hi ({lo}>{hi})")

    # 3) если есть диапазон, базовое значение должно быть числом (кроме булевых/строковых спец-ключей)
    for k in ranges.keys():
        if k not in base:
            errs.append(f"ranges: ключ '{k}' отсутствует в base")
            continue
        v = base.get(k)
        if not _is_num(v):
            errs.append(f"base: ключ '{k}' (есть в ranges) должен быть числом, сейчас {v!r}")

    # 4) строковые режимы
    def _check_enum(key: str, allowed: set):
        if key in base:
            v = base.get(key)
            if not _is_nonempty_str(v):
                errs.append(f"режим '{key}': пустая/некорректная строка: {v!r}")
            else:
                vv = str(v).strip()
                if vv not in allowed:
                    errs.append(f"режим '{key}': {vv!r} не в {sorted(list(allowed))}")

    _check_enum("термодинамика", ALLOWED_THERMO)
    _check_enum("газ_модель_теплоемкости", ALLOWED_CP_MODEL)
    _check_enum("модель_пассивного_расхода", ALLOWED_PASSIVE_FLOW)
    _check_enum("стенка_термомодель", ALLOWED_WALL_MODEL)

    # стенка_форма допускает synonyms по startswith('cyl')
    if "стенка_форма" in base:
        v = base.get("стенка_форма")
        if not _is_nonempty_str(v):
            errs.append(f"режим 'стенка_форма': пустая/некорректная строка: {v!r}")
        else:
            vv = str(v).strip().lower()
            if vv not in ALLOWED_WALL_SHAPE and not vv.startswith("cyl") and vv != "sphere":
                errs.append(f"режим 'стенка_форма': {vv!r} не распознан (ожидали sphere/cyl*)")

    if "стенка_h_газ_режим" in base:
        v = base.get("стенка_h_газ_режим")
        if not _is_nonempty_str(v):
            errs.append(f"режим 'стенка_h_газ_режим': пустая/некорректная строка: {v!r}")
        else:
            vv = str(v).strip()
            if vv not in ALLOWED_H_GW_MODE:
                errs.append(f"режим 'стенка_h_газ_режим': {vv!r} не в {sorted(list(ALLOWED_H_GW_MODE))}")

    # 5) булевые переключатели
    for key in [
        "ISO_auto_C_from_Qn_camozzi",
        "использовать_паспорт_компонентов",
        "стенка_auto_по_объёму",
        "стенка_h_учитывать_dV",
    ]:
        if key in base and not _is_bool(base.get(key)):
            errs.append(f"bool '{key}': ожидается True/False, сейчас {base.get(key)!r}")

    # 6) паспорт компонентов
    if base.get("использовать_паспорт_компонентов", False):
        pj = base.get("паспорт_компонентов_json", "")
        if not _is_nonempty_str(pj):
            errs.append(f"паспорт: 'паспорт_компонентов_json' пуст/некорректен: {pj!r}")
        # существование проверим на уровне main(), потому что нужен root path

    return errs


def main() -> int:
    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    base_path = root / "default_base.json"
    ranges_path = root / "default_ranges.json"

    if not base_path.exists():
        print(f"!! Не найден {base_path}")
        return 2
    if not ranges_path.exists():
        print(f"!! Не найден {ranges_path}")
        return 2

    base = _load_json(base_path)
    ranges = _load_json(ranges_path)

    if not isinstance(base, dict):
        print("!! default_base.json должен быть объектом (dict)")
        return 2
    if not isinstance(ranges, dict):
        print("!! default_ranges.json должен быть объектом (dict)")
        return 2

    errs = check_base_and_ranges(base, ranges)

    # Проверка существования паспорта (если включен)
    if base.get("использовать_паспорт_компонентов", False):
        pj = str(base.get("паспорт_компонентов_json", ""))
        ppath = (root / pj).resolve() if not Path(pj).is_absolute() else Path(pj)
        if not ppath.exists():
            errs.append(f"паспорт: файл не найден: {pj} -> {ppath}")

    if errs:
        print("\nПроблемы контрактов параметров:")
        for e in errs:
            print(" -", e)
        print("\nИТОГ: FAIL")
        return 1

    print("Контракты параметров: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
