# Bundle analysis — R31S grid/cadence follow-up (2026-03-24)

## Input
- Bundle: `7a572387-4a18-4608-a2f3-d8986c69e809.zip`
- Release: `PneumoApp_v6_80_R176_R31S_2026-03-24`

## What the bundle already proved
- Old GL detached-layout crash-path did not return.
- Strict loglint did not regress.
- 3D FPS was reported as acceptable by user feedback.

## What remained broken in R31S
### Road wire-grid spacing was still unstable
Bundle-side check measured:
- minimum spacing: **0.180905 m**
- maximum spacing: **1.059108 m**
- unique rounded values over the run: **612**

Representative frames:
- frame 0: spacing `0.807449 m`, n_long `720`, cross_stride `11`, window `0.000..52.778 m`
- frame 100: spacing `0.991037 m`, n_long `720`, cross_stride `11`, window `1.889..66.667 m`
- frame 800: spacing `1.048387 m`, n_long `652`, cross_stride `10`, window `99.806..168.056 m`
- frame 1190: spacing `0.201156 m`, n_long `200`, cross_stride `3`, window `165.823..179.167 m`

That is not a constant world grid. It explains the user-visible feeling that the grid moved with a different speed/spacing than the road.

### Auxiliary panes still lacked quantitative acceptance evidence
The bundle did not contain pane-level redraw cadence metrics, so detached-pane smoothness could not be proven numerically even after the R31S scheduler fix.

## R31T response
- road grid spacing now comes from a bundle/view-stable helper instead of the instantaneous playback window;
- auxiliary pane cadence floor raised;
- `AnimatorAuxCadence` telemetry added for future bundles.

Reference stable spacing from the same speed profile under the new helper:
- viewport 960 px → `1.25 m`
- viewport 1280 px → `0.95 m`
- viewport 1600 px → `0.75 m`
