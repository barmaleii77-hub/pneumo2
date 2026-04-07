# Bundle analysis — road/speed regression (R31R)
Исходный bundle: `4baf7ead-7cf9-47e7-9c54-50c85ef7c6ca.zip` / release `R31Q`.
Найденный корень: окно 3D-дороги выходило за реальный диапазон `s_world/road_profile`, `np.interp` прижимал значения к endpoint и рождал repeated longitudinal slices. Это давало degenerate GL faces, warning `MeshData invalid value encountered in divide` и лишнюю нагрузку на playback.

## Representative frames
### frame=0
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 727 | 15 | 20328 | 3725 | 134 |
| fixed | 721 | 15 | 20160 | 0 | 0 |
| play | 720 | 11 | 14380 | 0 | 0 |
| play_many | 420 | 9 | 6704 | 0 | 0 |

### frame=1
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 729 | 15 | 20384 | 3697 | 133 |
| fixed | 723 | 15 | 20216 | 0 | 0 |
| play | 720 | 11 | 14380 | 0 | 0 |
| play_many | 420 | 9 | 6704 | 0 | 0 |

### frame=10
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 745 | 15 | 20832 | 3389 | 122 |
| fixed | 739 | 15 | 20664 | 0 | 0 |
| play | 720 | 11 | 14380 | 0 | 0 |
| play_many | 420 | 9 | 6704 | 0 | 0 |

### frame=100
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 786 | 15 | 21980 | 0 | 0 |
| fixed | 786 | 15 | 21980 | 0 | 0 |
| play | 720 | 11 | 14380 | 0 | 0 |
| play_many | 420 | 9 | 6704 | 0 | 0 |

### frame=500
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 786 | 15 | 21980 | 0 | 0 |
| fixed | 786 | 15 | 21980 | 0 | 0 |
| play | 720 | 11 | 14380 | 0 | 0 |
| play_many | 420 | 9 | 6704 | 0 | 0 |

### frame=1000
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 423 | 15 | 11816 | 4705 | 169 |
| fixed | 418 | 15 | 11676 | 0 | 0 |
| play | 418 | 11 | 8340 | 0 | 0 |
| play_many | 418 | 9 | 6672 | 0 | 0 |

### frame=1199
| mode | n_long | n_lat | faces | degenerate_faces | duplicate_slices |
| --- | ---: | ---: | ---: | ---: | ---: |
| orig | 240 | 15 | 6692 | 5405 | 194 |
| fixed | 240 | 15 | 6692 | 0 | 0 |
| play | 180 | 11 | 3580 | 0 | 0 |
| play_many | 140 | 9 | 2224 | 0 | 0 |

## Verdict
- `fixed`: degenerate faces -> `0` на representative start/end frames.
- `play`: mesh становится легче во время playback без возврата к ложной редкой дороге.
- `play_many`: при множестве открытых dock-панелей faces дополнительно режутся для FPS-budget.
