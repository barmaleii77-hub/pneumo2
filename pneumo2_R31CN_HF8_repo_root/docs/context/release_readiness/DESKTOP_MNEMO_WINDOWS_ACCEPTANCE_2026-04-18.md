# Desktop Mnemo Windows Acceptance 2026-04-18

Purpose: record the Desktop Mnemo Windows acceptance hardening pass for
startup, close-return, local timer shutdown and truth/unavailable-state
visibility. This note is automated runtime evidence plus explicit manual
checklist boundaries; it is not final Windows visual acceptance closure.

## Source Branch

- Base/trunk: `codex/work` tracking `origin/codex/work`
- Working state: dirty Mnemo-owned changes in the primary worktree
- Scope: `pneumo_solver_ui/desktop_mnemo/*`,
  `tests/test_desktop_mnemo_*`, and this Mnemo-specific release note.

## Automated Runtime Proof Commands

```powershell
cd C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = "workspace\runtime_proof_next_step\mnemo_windows_acceptance_$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null
python -m pneumo_solver_ui.desktop_mnemo.main --runtime-proof $out --runtime-proof-startup-budget-s 3.0
python -m pneumo_solver_ui.desktop_mnemo.main --runtime-proof-validate "$out\desktop_mnemo_runtime_proof.json"
```

```powershell
cd C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = "workspace\runtime_proof_next_step\mnemo_offscreen_acceptance_$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null
python -m pneumo_solver_ui.desktop_mnemo.main --runtime-proof $out --runtime-proof-offscreen --runtime-proof-startup-budget-s 3.0
python -m pneumo_solver_ui.desktop_mnemo.main --runtime-proof-validate "$out\desktop_mnemo_runtime_proof.json"
```

## Results

| proof | qt_platform | status | release_readiness | constructor_s | first_event_cycle_s | close_s | validation |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Real Windows | `windows` | `PASS` | `PENDING_REAL_WINDOWS_VISUAL_CHECK` | `0.330057` | `0.548019` | `0.012398` | `ok=true`, no missing/failed checks, no missing manual items |
| Offscreen CI-style | `offscreen` | `PASS` | `PENDING_REAL_WINDOWS_VISUAL_CHECK` | `0.120630` | `0.268311` | `0.009343` | `ok=true`, no missing/failed checks, no missing manual items |

Artifact paths:

- `workspace/runtime_proof_next_step/mnemo_windows_acceptance_20260418_114408/desktop_mnemo_runtime_proof.json`
- `workspace/runtime_proof_next_step/mnemo_windows_acceptance_20260418_114408/desktop_mnemo_runtime_proof.md`
- `workspace/runtime_proof_next_step/mnemo_offscreen_acceptance_20260418_114418/desktop_mnemo_runtime_proof.json`
- `workspace/runtime_proof_next_step/mnemo_offscreen_acceptance_20260418_114418/desktop_mnemo_runtime_proof.md`

The `workspace/` artifact layer is gitignored and remains temporary evidence
unless copied or regenerated into the durable release/SEND evidence location.

## Automated Coverage Added

- Runtime proof now requires positive window geometry and native canvas size.
- Runtime proof now requires status/truth text visibility and verifies blank
  startup remains `Mnemo: unavailable pressure/state`, not fake confirmed truth.
- Runtime proof now records visible blocking modal dialogs and requires none.
- Runtime proof closes the window through Qt, records `close_s`, and requires
  close-return under `1.0s`.
- Runtime proof requires the window to be hidden after close and local Desktop
  Mnemo playback/pointer timers to be stopped.
- `MnemoMainWindow.closeEvent` now stops Desktop Mnemo runtime activity before
  persisting window state.

## Validation

```powershell
python -m pytest tests/test_desktop_mnemo_dataset_contract.py tests/test_desktop_mnemo_inline_overlay_contract.py tests/test_desktop_mnemo_launcher_contract.py tests/test_desktop_mnemo_main_contract.py tests/test_desktop_mnemo_page_contract.py tests/test_desktop_mnemo_runtime_proof.py tests/test_desktop_mnemo_settings_bridge_contract.py tests/test_desktop_mnemo_snapshot_contract.py tests/test_desktop_mnemo_window_contract.py tests/test_pneumo_scheme_mnemo_cache_resource_contract.py -q
python -m compileall -q pneumo_solver_ui/desktop_mnemo
```

Result:

- `26 passed`
- Expected Qt deprecation warnings remain from
  `QTableWidgetItem.setTextAlignment`.
- `compileall` passed.

## Manual Checks Still Pending

- Real Windows open/no-hang observation by an operator.
- Resize, maximize/restore and Snap/restore visual inspection.
- Dock overlap/occlusion inspection after real resize operations.
- Scheme readability and truth/unavailable indicator visibility in the actual
  Windows session.
- Second-monitor and mixed-DPI movement if hardware is available.
- Long-running follow/playback stability.

## Non-Claims

- This does not close final Windows visual acceptance without manual evidence.
- This does not close Snap Layouts, second-monitor, mixed-DPI or long-running
  stability gates.
- This does not close producer truth, geometry, packaging, Animator, Compare
  Viewer, shell, diagnostics/SEND or `OG-001` through `OG-006`.
- This does not invent pressure/state/geometry data; missing or degraded
  surfaces remain visible as unavailable/warning states.
