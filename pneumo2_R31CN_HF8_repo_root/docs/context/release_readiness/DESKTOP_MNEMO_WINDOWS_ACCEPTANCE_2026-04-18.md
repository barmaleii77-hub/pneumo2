# Desktop Mnemo Windows Acceptance 2026-04-18

Purpose: record the Desktop Mnemo Windows acceptance hardening pass for
startup, close-return, local timer shutdown and truth/unavailable-state
visibility. This note is automated runtime evidence plus explicit manual
checklist boundaries; it is not final Windows visual acceptance closure.

## Source Branch

- Base/trunk before implementation: `codex/work` tracking `origin/codex/work`;
  `git fetch --all --prune` completed before implementation.
- Implementation branch: `codex/desktop-mnemo-v38-acceptance`, reusing the
  existing branch at the same commit as `origin/codex/work`.
- Working state at implementation start: shared worktree was dirty, but the
  Mnemo-owned dirty scope was limited to this note and
  `tests/test_desktop_mnemo_launcher_contract.py`. Non-Mnemo dirty Compare,
  Input and shell files were excluded from this pass.
- Scope: `pneumo_solver_ui/desktop_mnemo/*`,
  `tests/test_desktop_mnemo_*`, and this Mnemo-specific release note.
- Commit caveat: local `7823dc2` is not an ancestor of current `HEAD`, and no
  local/remote branch currently contains it. Do not merge/cherry-pick it; it is
  a mixed GUI quarantine commit. The Mnemo-owned behavior from that pass is
  present in the current code through `d7d76f5`.

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
| Real Windows | `windows` | `PASS` | `PENDING_REAL_WINDOWS_VISUAL_CHECK` | `0.305822` | `0.538086` | `0.019270` | `ok=true`, no missing/failed checks, no missing manual items |
| Offscreen CI-style | `offscreen` | `PASS` | `PENDING_REAL_WINDOWS_VISUAL_CHECK` | `0.087518` | `0.174777` | `0.006995` | `ok=true`, no missing/failed checks, no missing manual items |

Artifact paths:

- `workspace/runtime_proof_next_step/mnemo_windows_acceptance_20260418_143258/desktop_mnemo_runtime_proof.json`
- `workspace/runtime_proof_next_step/mnemo_windows_acceptance_20260418_143258/desktop_mnemo_runtime_proof.md`
- `workspace/runtime_proof_next_step/mnemo_offscreen_acceptance_20260418_143306/desktop_mnemo_runtime_proof.json`
- `workspace/runtime_proof_next_step/mnemo_offscreen_acceptance_20260418_143306/desktop_mnemo_runtime_proof.md`

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
- Shell/catalog visibility is covered by a Mnemo-owned launcher contract test:
  `desktop_mnemo` must remain an external Qt `specialized_window`, with derived
  source-of-truth role, standalone module
  `pneumo_solver_ui.desktop_mnemo.main`, and command-search aliases `mnemo`,
  `мнемосхема` and `пневмосхема`.

## V38 Visual/Pipeline Boundary

- `python -m pneumo_solver_ui.tools.desktop_main_shell_qt --list-tools`
  reported `desktop_mnemo` as `Внешние окна / Мнемосхема / qt / derived`.
- The V38 optimized pipeline remains `INPUTS -> RING -> SUITE -> BASE -> OPT
  -> ANALYSIS -> ANIMATOR/DIAGNOSTICS`; Desktop Mnemo is treated as a
  specialized visualization/evidence consumer, not an authoring step in the
  `INPUTS -> RING -> SUITE` flow.
- This pass did not embed or duplicate Mnemo inside the shell. Shell/search can
  route to `desktop_mnemo`, while the actual scheme surface remains the
  separate Desktop Mnemo top-level window.
- Manual operator visual inspection from
  `python -m pneumo_solver_ui.tools.desktop_main_shell_qt --open desktop_mnemo`
  still remains pending; this note does not claim human-visible no-overlap,
  Snap/restore or second-monitor acceptance.

## Manual V38 Operator Check

Outcome: `MANUAL_VISIBLE_STARTUP_CLOSE_CHECK_RECORDED`, not final Windows
visual acceptance closure.

- Timestamp: `2026-04-18 15:11:45 +05:00`.
- Branch: `codex/desktop-mnemo-v38-acceptance`.
- Command:
  `python -m pneumo_solver_ui.tools.desktop_main_shell_qt --open desktop_mnemo`.
- Screenshot/process artifacts:
  - `workspace/manual_v38_operator_check/mnemo_manual_20260418_151004/desktop_after_open.png`
  - `workspace/manual_v38_operator_check/mnemo_manual_20260418_151132/desktop_after_open.png`
  - `workspace/manual_v38_operator_check/mnemo_manual_20260418_151132/manual_launch_processes.json`
- Observed: shell launched as a separate top-level window and opened Desktop
  Mnemo as a separate top-level `Мнемосхема пневмосистемы` window; Mnemo was
  not embedded in shell.
- Observed: Desktop Mnemo displayed a specialized scheme/unavailable-state
  surface with the large pneumatic scheme area and operator controls, not a
  generic service-status panel.
- Observed: blank startup kept unavailable truth visible; screenshot evidence
  showed `Mnemo: unavailable pressure/state` and no fake `Mnemo: confirmed`.
- Observed: normal close was exercised through Windows `CloseMainWindow` for
  both `PneumoApp - Рабочее место инженера` and `Мнемосхема пневмосистемы`;
  both exited after close, with `force_stopped=false`.
- Pending: resize/maximize/restore, Snap/restore, dock overlap/occlusion,
  second-monitor/mixed-DPI movement and long-running follow/playback stability
  were not closed by this check.

## Validation

```powershell
python -m pytest tests/test_desktop_mnemo_runtime_proof.py tests/test_desktop_mnemo_window_contract.py tests/test_desktop_mnemo_dataset_contract.py tests/test_desktop_mnemo_launcher_contract.py tests/test_desktop_mnemo_settings_bridge_contract.py tests/test_desktop_mnemo_snapshot_contract.py -q
python -m compileall -q pneumo_solver_ui/desktop_mnemo
python -m pneumo_solver_ui.tools.desktop_main_shell_qt --list-tools
```

Result:

- Full focused run: `22 passed`.
- Expected Qt deprecation warnings remain from
  `QTableWidgetItem.setTextAlignment`.
- `compileall` passed.
- `git diff --check` passed for the Mnemo-owned test and release note edits.

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
- Temporary `workspace/` proof artifacts are not durable release/SEND evidence
  until copied or regenerated into the expected durable release/SEND evidence
  location.
