# TODO / WISHLIST addendum — R31AI — 2026-03-26

## Что закрыто в этом проходе

- Свежий Windows SEND bundle разобран глубоко: подтверждены реальные `OpenGL GLError` во время drag/resize/floating live 3D и провал playback cadence примерно до 0.9–1.0 Hz при 11 видимых панелях.
- Live GL layout guard переведён на dock-only observation; child GL viewport события больше не разгоняют лавину layout-transition callbacks.
- На время floating move/resize 3D viewport действительно suspend/hide + placeholder, чтобы не рисовать через нестабильный GL context path.
- Playback service timer и cadence budget auxiliary panes ужесточены в пользу 3D, а active road mesh стал легче в playback/perf mode.

## Что остаётся P0

- Живая Windows acceptance уже на R31AI: убедиться, что drag/resize/floating/re-dock больше не даёт `OpenGL GLError` и не подвешивает весь Animator.
- Подтвердить по следующему SEND bundle, что cadence playback на `speed=1.0` заметно вырос и больше не деградирует к ~1 Hz при большом числе видимых панелей.
- Web UI CPU acceptance не смешивать с Desktop Animator performance: это отдельный трек и отдельный proof bundle.
