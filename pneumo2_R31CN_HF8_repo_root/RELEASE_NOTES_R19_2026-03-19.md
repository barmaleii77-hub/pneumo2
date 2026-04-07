# Release Notes — R19

Release: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R19_2026-03-19`

## Hotfixes

- launcher now starts Streamlit with `--server.address 127.0.0.1`;
- launcher waits for real HTTP readiness (`/_stcore/health` or `/`) instead of only checking that a TCP port is open;
- launcher opens browser using `http://127.0.0.1:<port>` and falls back to `os.startfile()` on Windows;
- root and package Streamlit configs bind to `127.0.0.1`;
- `pneumo_solver_ui/tools/launch_ui.py` aligned with the same address rule.

## Rationale

User bundles from R18 showed that the browser window opened, but the page did not become available.
R18 launcher only checked for an open port and used `localhost`, which could produce false positives and host-resolution issues on Windows.

