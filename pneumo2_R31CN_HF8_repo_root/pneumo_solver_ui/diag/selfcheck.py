"""Самопроверка окружения и целостности пакета.

Задачи:
- Быстро (обычно ≤1–2 сек) обнаружить типовые проблемы установки/сборки.
- Дать понятные сообщения пользователю.
- Не требует интернет-доступа.

Важно: это НЕ "экспертный режим". Это встроенная страховка качества.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
import importlib
import platform
import sys
from typing import Any


@dataclass
class SelfcheckResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    info: dict[str, str]


def _try_import_version(module_name: str) -> str | None:
    try:
        mod = importlib.import_module(module_name)
        return str(getattr(mod, "__version__", "unknown"))
    except Exception:
        return None


def run_selfcheck(root_dir: str | Path) -> dict[str, Any]:
    """Запускает лёгкую самопроверку.

    Args:
        root_dir: корень приложения (папка, где лежат CORE/ и pneumo_solver_ui/).

    Returns:
        dict с полями ok/errors/warnings/info.
    """

    root = Path(root_dir).resolve()

    errors: list[str] = []
    warnings: list[str] = []
    info: dict[str, str] = {
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "root": str(root),
    }

    # Python
    if sys.version_info < (3, 10):
        errors.append(
            f"Требуется Python 3.10+ (или выше). Текущая версия: {info['python']}."
        )

    # Пакеты
    required = ["streamlit", "numpy", "pandas"]
    optional = ["scipy", "plotly", "psutil"]

    for name in required:
        ver = _try_import_version(name)
        if ver is None:
            errors.append(
                f"Не найден пакет: {name}. Установите зависимости (INSTALL_WINDOWS.bat или pip install -r requirements.txt)."
            )
        else:
            info[name] = ver

    for name in optional:
        ver = _try_import_version(name)
        if ver is None:
            warnings.append(
                f"Опционально: пакет {name} не найден. Часть функций может быть недоступна."
            )
        else:
            info[name] = ver

    # Структура проекта
    path_checks = [
        ("CORE", "ядро расчёта (CORE)"),
        ("pneumo_solver_ui", "интерфейс (pneumo_solver_ui)"),
        ("pneumo_solver_ui/components/mech_car3d/index.html", "3D-анимация (mech_car3d)"),
        ("pneumo_solver_ui/components/mech_car2d/index.html", "2D-анимация (mech_car2d)"),
        ("pneumo_solver_ui/components/plotly_events/__init__.py", "события Plotly (plotly_events)"),
    ]

    for rel, desc in path_checks:
        p = root / rel
        if not p.exists():
            if rel in ("CORE", "pneumo_solver_ui"):
                errors.append(
                    f"Не найдено: {rel} — {desc}. Пакет приложения повреждён/неполный."
                )
            else:
                warnings.append(
                    f"Не найдено: {rel} — {desc}. Соответствующая функция может не работать."
                )

    ok = len(errors) == 0
    return asdict(SelfcheckResult(ok=ok, errors=errors, warnings=warnings, info=info))
