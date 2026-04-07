# Bundle analysis — R31X regressions (2026-03-24)

- Bundle release: `PneumoApp_v6_80_R176_R31X_2026-03-24`
- NPZ: `/mnt/data/bundle_latest2/ui_sessions/UI_20260325_002253/workspace/exports/anim_latest.npz`
- Startup warning present: **True**
- Startup warning line: `[2026-03-25T00:35:31] AnimatorWarning: Animator starts with auxiliary docks attached for stability. After first show side panels are re-tiled against current screen metrics; live 3D GL uses a dedicated top-level window from launch instead of floating QDockWidget mode. {'code': 'startup_external_gl_window', 'context': {}}`

## Cylinder mount-point check

The user asked whether the visible balls were frame mounts and whether cylinder attachment points were inverted. The bundle says otherwise:
- ЛП / C1: `cyl1_bot` is closest to **upper_front** at 10.4 mm; second closest = upper_rear at 104.0 mm. `cyl*_top` remains frame-side.
- ЛП / C2: `cyl2_bot` is closest to **upper_rear** at 10.4 mm; second closest = upper_front at 104.0 mm. `cyl*_top` remains frame-side.
- ПП / C1: `cyl1_bot` is closest to **upper_front** at 10.4 mm; second closest = lower_front at 89.6 mm. `cyl*_top` remains frame-side.
- ПП / C2: `cyl2_bot` is closest to **upper_rear** at 10.3 mm; second closest = lower_rear at 89.7 mm. `cyl*_top` remains frame-side.
- ЛЗ / C1: `cyl1_bot` is closest to **upper_front** at 10.3 mm; second closest = upper_rear at 103.9 mm. `cyl*_top` remains frame-side.
- ЛЗ / C2: `cyl2_bot` is closest to **upper_rear** at 10.4 mm; second closest = upper_front at 103.9 mm. `cyl*_top` remains frame-side.
- ПЗ / C1: `cyl1_bot` is closest to **upper_front** at 10.5 mm; second closest = lower_front at 99.3 mm. `cyl*_top` remains frame-side.
- ПЗ / C2: `cyl2_bot` is closest to **upper_rear** at 10.4 mm; second closest = lower_rear at 99.4 mm. `cyl*_top` remains frame-side.

Conclusion: exported mount points are consistent with the project law “цилиндр к раме, шток к рычагу”. The misleading yellow balls were consumer-side debug piston markers, not frame mounts.

## Initial piston position sanity check

- ЛП / C1: `stroke0=0.1257 m`, piston fraction from top at t0 = `0.487`
- ПП / C1: `stroke0=0.1243 m`, piston fraction from top at t0 = `0.492`
- ЛЗ / C1: `stroke0=0.1243 m`, piston fraction from top at t0 = `0.492`
- ПЗ / C1: `stroke0=0.1257 m`, piston fraction from top at t0 = `0.487`
- ЛП / C2: `stroke0=0.1257 m`, piston fraction from top at t0 = `0.496`
- ПП / C2: `stroke0=0.1243 m`, piston fraction from top at t0 = `0.502`
- ЛЗ / C2: `stroke0=0.1243 m`, piston fraction from top at t0 = `0.501`
- ПЗ / C2: `stroke0=0.1257 m`, piston fraction from top at t0 = `0.496`

These values are all about **0.49–0.50**, so at the start of the bundle pistons are visually expected near the middle, not pinned to the arm. That again points to the old visual consumer path / marker confusion, not to a bad exported static state.

## UX / runtime regression confirmed from logs

- The bundle still logs `startup_external_gl_window`, i.e. the old forced “external GL from launch” policy. This matches the user report that 3D did not dock back to the rest of the windows.
- The new patch therefore changes startup policy back to **docked-by-default** and keeps the safe external GL window only for explicit detach flows.
