from __future__ import annotations

from pneumo_solver_ui.optimization_packaging_snapshot_ui import (
    has_packaging_snapshot,
    render_packaging_snapshot_summary,
)
from pneumo_solver_ui.optimization_run_history import OptimizationRunPackagingSnapshot


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def metric(self, *args, **kwargs):
        return None


class _FakeSt:
    def __init__(self):
        self.captions = []
        self.markdowns = []
        self.warnings = []

    def caption(self, text):
        self.captions.append(str(text))

    def markdown(self, text):
        self.markdowns.append(str(text))

    def warning(self, text):
        self.warnings.append(str(text))

    def metric(self, *args, **kwargs):
        return None

    def columns(self, n):
        return [_FakeColumn() for _ in range(int(n))]


def test_has_packaging_snapshot_is_false_for_empty_snapshot() -> None:
    assert not has_packaging_snapshot(OptimizationRunPackagingSnapshot())


def test_render_packaging_snapshot_summary_handles_compact_and_full_modes() -> None:
    snapshot = OptimizationRunPackagingSnapshot(
        rows_considered=3,
        rows_with_packaging=2,
        packaging_complete_rows=1,
        packaging_truth_ready_rows=1,
        packaging_verification_pass_rows=2,
        runtime_fallback_rows=1,
        spring_host_interference_rows=0,
        spring_pair_interference_rows=1,
        status_counts=(("complete", 1), ("shared_axle_fallback", 1)),
    )

    st_full = _FakeSt()
    assert render_packaging_snapshot_summary(
        st_full,
        snapshot,
        compact=False,
        heading="Сводка по геометрии узлов (выбранный run)",
        interference_prefix="В выбранном run есть признаки пересечений по геометрии узлов",
    )
    assert any("Сводка по геометрии узлов (выбранный run)" in text for text in st_full.markdowns)
    assert any("Статусы по строкам" in text for text in st_full.captions)
    assert any("В выбранном run есть признаки пересечений по геометрии узлов" in text for text in st_full.warnings)

    st_compact = _FakeSt()
    assert render_packaging_snapshot_summary(st_compact, snapshot, compact=True)
    assert any("Геометрия узлов:" in text for text in st_compact.captions)
    assert any("Пересечения:" in text for text in st_compact.captions)
