# Desktop Startup Visible Proof 2026-04-17

Purpose: record the controlled real-Windows startup proof for the Qt main shell
and Desktop Mnemo after the startup/runtime-proof hardening pass.

This note is evidence of visible-window automated startup only. It is not a
final Windows visual acceptance claim and does not close Snap Layouts,
second-monitor, mixed-DPI, long-running event-loop or operator visual review
gates.

## Source Commands

```powershell
$out='workspace\runtime_proof_next_step\qt_shell_visible'
New-Item -ItemType Directory -Force -Path $out | Out-Null
python -m pneumo_solver_ui.tools.desktop_main_shell_qt --runtime-proof $out
```

```powershell
$out='workspace\runtime_proof_next_step\mnemo_visible'
New-Item -ItemType Directory -Force -Path $out | Out-Null
python -m pneumo_solver_ui.desktop_mnemo.main --runtime-proof $out
```

```powershell
python -m pneumo_solver_ui.tools.desktop_main_shell_qt --runtime-proof-validate workspace\runtime_proof_next_step\qt_shell_visible\qt_main_shell_runtime_proof.json
python -m pneumo_solver_ui.desktop_mnemo.main --runtime-proof-validate workspace\runtime_proof_next_step\mnemo_visible\desktop_mnemo_runtime_proof.json
```

## Results

| surface | qt_platform | offscreen | automated_status | release_readiness | timing | layout evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Qt main shell | `windows` | `false` | `PASS` | `PENDING_MANUAL_VERIFICATION` | validator accepted visible startup | 3 docks, 9 menus |
| Desktop Mnemo | `windows` | `false` | `PASS` | `PENDING_REAL_WINDOWS_VISUAL_CHECK` | constructor `0.455488s`, first event cycle `0.675123s` | 8 docks |

## Artifact Paths

- `workspace/runtime_proof_next_step/qt_shell_visible/qt_main_shell_runtime_proof.json`
- `workspace/runtime_proof_next_step/qt_shell_visible/qt_main_shell_runtime_proof.md`
- `workspace/runtime_proof_next_step/mnemo_visible/desktop_mnemo_runtime_proof.json`
- `workspace/runtime_proof_next_step/mnemo_visible/desktop_mnemo_runtime_proof.md`

The `workspace/` artifact layer is intentionally gitignored. Before a release
SEND bundle, copy or regenerate the proof JSON/MD files into the named release
evidence location expected by diagnostics/SEND tooling.

## Validation Notes

- Qt main shell validator result: `ok=true`, automated checks passed, warning
  remains for manual Snap/DPI/second-monitor verification.
- Desktop Mnemo validator result: `ok=true`, automated checks passed, warning
  remains for real Windows visual/no-hang verification.
- The Mnemo proof ran on the real Windows Qt platform, not the offscreen
  platform, and exited via runtime-proof flow instead of a permanent
  `app.exec()` loop.

## Interpretation

- This narrows the immediate "window opens and does not hang during startup"
  confidence gap for the Qt shell and Desktop Mnemo.
- This does not prove long-running operator stability, correctness of all
  drawings, absence of all visual overlaps, Snap Layout behavior, per-monitor
  DPI migration or second-monitor workflows.
- Open release gates still require operator-visible Windows acceptance and
  named release artifacts before final closure.

## Next Actions

- Run the manual Windows visual checklist for Qt main shell and Desktop Mnemo:
  open, resize, Snap, restore, move across monitors, mixed-DPI if available,
  inspect dock overlaps, then close normally.
- If the manual pass is clean, promote the proof artifacts into the release
  evidence/SEND-bundle path and record the exact durable artifact locations.
- Keep `PENDING_MANUAL_VERIFICATION` and `PENDING_REAL_WINDOWS_VISUAL_CHECK`
  until that manual pass exists as durable evidence.
