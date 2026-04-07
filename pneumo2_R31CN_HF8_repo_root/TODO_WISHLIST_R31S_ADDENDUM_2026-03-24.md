# TODO / WISHLIST addendum — R31S (2026-03-24)

## Done
- Устранён starvation-path auxiliary panes в Desktop Animator playback: visible окна больше не обновляются по одному в ultra-low cadence.
- Visible road wire-grid переведена на world-anchored выбор cross-bars по longitudinal `s`, без viewport-phase drift относительно самой дороги.
- Контекст проекта обновлён: R31S фиксирует уже не OpenGL FPS, а живость остальных окон и визуальную фиксацию дорожной сетки к дороге.

## Still open
- Живой Windows retest на `R31S` с новым SEND bundle.
- Canonical `road_width_m` в export/meta.
- Measured browser/Windows perf acceptance.
- Solver-points completeness / cylinder packaging contract.
