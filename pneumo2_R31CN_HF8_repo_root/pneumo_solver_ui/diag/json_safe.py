# -*- coding: utf-8 -*-
"""pneumo_solver_ui.diag.json_safe

Мини-набор утилит для *строгого JSON* в логах.

Зачем
-----
Проект опирается на JSONL (один JSON-объект на строку) для пост-мортем анализа.
По умолчанию Python `json.dumps` допускает NaN/Inf, что **не является** строгим JSON,
если не передать `allow_nan=False`. Также в поле логов часто попадают объекты,
которые не сериализуются напрямую (Path, bytes, numpy scalar/arrays, Exception и т.п.).

Эти функции:
- приводят значения к JSON-совместимому виду (best-effort);
- заменяют NaN/Inf на None;
- делают `json.dumps(..., allow_nan=False)` безопасным для production.

Важно
------
Модуль должен быть лёгким и не тащить зависимости. NumPy импортируется опционально.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def to_jsonable(x: Any) -> Any:
    """Best-effort конвертация к JSON-совместимому виду.

    - NaN/Inf -> None
    - Path -> str
    - bytes -> utf-8 str (errors=replace)
    - numpy scalar/arrays -> python types/list (если numpy доступен)
    - dict/list/tuple/set -> рекурсивно
    - Exception -> repr
    - иначе -> str
    """

    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return bool(x)
        if isinstance(x, int):
            return int(x)
        if isinstance(x, float):
            try:
                if not math.isfinite(float(x)):
                    return None
            except Exception:
                return None
            return float(x)
        if isinstance(x, str):
            return x
        if isinstance(x, Path):
            return str(x)
        if isinstance(x, bytes):
            try:
                return x.decode("utf-8", errors="replace")
            except Exception:
                return repr(x)

        # numpy scalar / array-like
        try:
            import numpy as _np  # type: ignore

            if isinstance(x, _np.generic):
                return to_jsonable(x.item())
        except Exception:
            pass

        if hasattr(x, "tolist"):
            try:
                return to_jsonable(x.tolist())  # type: ignore[attr-defined]
            except Exception:
                pass

        if isinstance(x, dict):
            return {str(k): to_jsonable(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [to_jsonable(v) for v in list(x)]
        if isinstance(x, Exception):
            return repr(x)

        return str(x)
    except Exception:
        return repr(x)


def json_dumps(obj: Any, *, indent: int | None = None) -> str:
    """Безопасный json.dumps для логов.

    Гарантия: возвращает строку и не бросает исключений.
    """
    try:
        return json.dumps(to_jsonable(obj), ensure_ascii=False, indent=indent, allow_nan=False)
    except Exception:
        try:
            return json.dumps({"_nonserializable": repr(obj)}, ensure_ascii=False, indent=indent, allow_nan=False)
        except Exception:
            return "{}"
