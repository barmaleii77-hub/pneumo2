from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools import clipboard_file


def test_windows_powershell_filelist_uses_sta(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.zip"
    sample.write_bytes(b"zip")

    calls = {}

    monkeypatch.setattr(clipboard_file.shutil, "which", lambda name: "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" if name == "powershell" else None)

    class Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **kwargs):
        calls["cmd"] = list(cmd)
        return Result()

    monkeypatch.setattr(clipboard_file.subprocess, "run", fake_run)

    ok, msg = clipboard_file._copy_windows_powershell_filelist(sample)
    assert ok is True
    assert "powershell" in msg.lower()
    assert "-STA" in calls["cmd"]
