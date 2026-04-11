from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_iso_network_bottleneck_report_runs_as_module_and_writes_report() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.iso_network_bottleneck_report"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "ISO bottleneck report saved:" in proc.stdout

    report_path = ROOT / "pneumo_solver_ui" / "reports" / "iso_network_bottlenecks.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "# ISO 6358 bottleneck report" in report_text
    assert "Лучший maximin-путь" in report_text
