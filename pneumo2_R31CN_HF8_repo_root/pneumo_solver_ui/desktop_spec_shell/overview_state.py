from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _latest_path(root: Path, patterns: tuple[str, ...]) -> Path | None:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(root.rglob(pattern))
    files = [path for path in matches if path.exists()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


@dataclass(frozen=True)
class OverviewCardState:
    title: str
    value: str
    detail: str
    command_id: str


@dataclass(frozen=True)
class OverviewSnapshot:
    cards: tuple[OverviewCardState, ...]


def build_overview_snapshot(repo_root: Path | None = None) -> OverviewSnapshot:
    root = repo_root or _repo_root()
    runs_root = root / "runs"
    desktop_root = Path.home() / "Desktop"
    baseline_path = _latest_path(runs_root, ("*baseline*.json", "*baseline*.npz", "*baseline*.csv")) if runs_root.exists() else None
    result_path = _latest_path(runs_root, ("*.npz", "summary*.json", "*results*.json")) if runs_root.exists() else None
    bundle_path = None
    if desktop_root.exists():
        bundle_path = _latest_path(desktop_root, ("SEND_*.zip", "*bundle*.zip"))

    pyside6_ready = find_spec("PySide6") is not None
    animator_ready = find_spec("pneumo_solver_ui.desktop_animator.app") is not None
    diagnostics_ready = (root / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").exists()
    workflow_graphs_ready = (
        (root / "docs" / "context" / "gui_spec_imports" / "current_pipeline.dot").exists()
        and (root / "docs" / "context" / "gui_spec_imports" / "optimized_pipeline.dot").exists()
    )

    cards = (
        OverviewCardState(
            title="Текущий проект",
            value=root.name,
            detail=str(root),
            command_id="workspace.input_data.open",
        ),
        OverviewCardState(
            title="Активный baseline",
            value=_safe_relative(baseline_path, root) if baseline_path else "Не выбран",
            detail="Источник истины по baseline должен жить в отдельном workspace.",
            command_id="workspace.baseline_run.open",
        ),
        OverviewCardState(
            title="Optimization contract",
            value="StageRunner - primary path",
            detail="Distributed coordinator остаётся advanced path и не должен конкурировать с основным запуском.",
            command_id="workspace.optimization.open",
        ),
        OverviewCardState(
            title="Последние результаты",
            value=_safe_relative(result_path, root) if result_path else "Пока нет артефактов",
            detail="Results and compare открываются из центра анализа результатов.",
            command_id="results.center.open",
        ),
        OverviewCardState(
            title="Последний diagnostics bundle",
            value=str(bundle_path.name) if bundle_path else "Пока нет ZIP",
            detail=str(bundle_path.parent) if bundle_path else "Глобальная диагностика должна оставаться доступной из любого workspace.",
            command_id="diagnostics.collect_bundle",
        ),
        OverviewCardState(
            title="Health / self-check",
            value=(
                f"PySide6={'OK' if pyside6_ready else 'missing'} | "
                f"Animator={'OK' if animator_ready else 'missing'} | "
                f"Diagnostics={'OK' if diagnostics_ready else 'missing'}"
            ),
            detail=(
                "Workflow graphs "
                + ("готовы" if workflow_graphs_ready else "не найдены")
                + "; shell должен сохранять честный bridge к существующим инженерным центрам."
            ),
            command_id="workspace.diagnostics.open",
        ),
    )
    return OverviewSnapshot(cards=cards)
