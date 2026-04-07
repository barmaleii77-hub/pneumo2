# RELEASE_NOTES_R31AI_2026-03-26

## Что это за релиз

R31AI — corrective release по **Desktop Animator playback/layout stability**.

Свежий Windows SEND bundle показал, что жалоба «при speed=1.0 кадров не хватает, а при манипуляции окнами всё виснет» имеет два связанных root cause:

1. **live GL layout churn** во время floating move/resize/re-dock, который вызывал реальные `OpenGL GLError` в `GLMeshItem` / `GLLinePlotItem`;
2. **playback overbudget** при большом числе видимых панелей, из-за чего cadence playback-панелей в bundle проваливалась примерно до `0.9–1.0 Hz`.

## Что исправлено

- live GL layout guard переведён на **dock-only observation**;
- внутренние Move/Resize/Show события child GL viewport больше не считаются полноценным trigger для layout transition;
- во время floating move/resize 3D viewport теперь действительно **suspend/hide + placeholder**, чтобы не рисовать через нестабильный GL context path;
- `QTimer` service cadence для playback tightened: на `speed >= 1.0` используется интервал **4 ms** вместо более редкого service wakeup;
- threshold `many visible docks` снижен до **8**, а cadence auxiliary panes сделан заметно жёстче в пользу live 3D;
- road mesh в 3D облегчается сильнее во время `playback/perf mode`, чтобы 3D playback не проигрывал CPU/GPU budget десяти соседним dock-панелям.

## Что не объявляется закрытым

- Этот релиз **не** объявляет закрытым Web UI idle CPU — это отдельный acceptance track.
- Этот релиз **не** отменяет предыдущие continuity/cylinder fixes; он адресует именно desktop-side playback/layout regression.

## Acceptance для следующего bundle

Следующий Windows SEND bundle на R31AI должен подтвердить:

- нет `OpenGL GLError` при drag/resize/floating/re-dock;
- playback на `speed=1.0` заметно живее и не проваливается к ~1 Hz при большом количестве видимых панелей;
- манипуляция окнами не приводит к тотальному подвисанию Animator.
