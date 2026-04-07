# TODO / Wishlist addendum — R31AE (2026-03-25)

## Closed in this pass

- Restored normal suite selection UX in both main and legacy editors; removed the forced empty-selection startup policy.
- Shipped default suite presets now start with all scenarios disabled, so a fresh page no longer triggers baseline work from an enabled default row.
- Manual ring-scenario creation remains intentionally enabled (`"включен": True`) so newly created scenarios are immediately actionable by explicit user intent.
- Raised Web UI idle sleep for follower components and embedded HTML widgets to `15 s / 30 s / 60 s`, keeping event-driven wake (`storage` / `focus` / `visibility`) as the primary activation path.
- Dense road surface and visible wire grid now both derive their longitudinal support from stable native dataset rows instead of relying primarily on frame-local visible-window resampling.
- Added explicit `cyl*_top` frame-mount markers in Desktop Animator and reduced housing-shell dominance to improve chamber / rod / piston readability.

## Still open

- Accept R31AE on a live Windows SEND bundle: verify browser idle CPU tail, resize/playback road stability, cylinder frame-side markers and overall cylinder readability on the real stack.
- Keep exporter-side cylinder packaging work open: true external body/gland points are still the clean path to fully honest housing-length rendering without fallback shells.
- Keep browser perf telemetry in the acceptance loop so post-run CPU regressions are proven by bundle data, not just by Task Manager impressions.
