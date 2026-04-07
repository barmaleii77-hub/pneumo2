# TODO / WISHLIST addendum — R31R (2026-03-24)

## Done
- Найден и устранён корень дорожного артефакта в Desktop Animator: out-of-range sampling больше не создаёт repeated endpoint slices и degenerate GL faces.
- Для Car3D добавлены playback density tiers (`play` / `play_many`) ради FPS во время проигрывания.
- Контекст проекта обновлён: R31Q дорожный артефакт больше не трактуется как «непонятная визуальная мелочь», а зафиксирован как конкретный interpolation-window bug.

## Still open
- Живой Windows retest на `R31R`.
- Canonical `road_width_m` в export/meta.
- Measured browser/Windows perf acceptance.
- Solver-points completeness / cylinder packaging contract.
