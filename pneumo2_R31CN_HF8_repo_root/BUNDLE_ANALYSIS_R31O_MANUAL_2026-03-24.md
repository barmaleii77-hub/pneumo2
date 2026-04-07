# Manual bundle analysis — R31O Windows run (2026-03-24)

## Input bundles

- `SEND_20260324_005743_manual_bundle.zip`
- `f0a52e21-f3fc-4eb8-9e23-0ad2820bdec1.zip`

Оба загруженных ZIP имеют одинаковый SHA256 и являются одним и тем же payload.

## Что подтверждено bundle-артефактами

- release: `PneumoApp_v6_80_R176_R31O_2026-03-23`
- platform: Windows 11 / Python 3.13.7
- SEND-bundle validation: **OK**
- `anim_latest`: **usable**
- geometry acceptance: **PASS**
- baseline/detail прогон завершился без solver-ошибок; detail export построен

## Что реально сломано

### Desktop Animator crash-path in detached layout

В run/session логах воспроизводится один и тот же сценарий:
- Desktop Animator стартует;
- при auto-detach / tiled detached layout 3D GL dock переводится в floating window;
- в `events.jsonl` и `desktop_animator_stdout.log` идут повторяющиеся `OpenGL.error.GLError` из `pyqtgraph.opengl`;
- дочерний процесс завершается с кодом `3221226505` (`0xC0000409`).

Это не похоже на проблему solver/export: `anim_latest.npz` присутствует и bundle-sidecar считает его usable.

## Что ещё обнаружено

### False strict-loglint seq failure

Bundle health фиксирует strict-loglint ошибки вида `non-monotonic seq`, но это ложный fail:
- parent UI и child Desktop Animator пишут в один session log;
- child процесс начинает `seq` заново с `1`;
- старый loglint ключевал последовательность только по `session_id`.

Следствие: multi-process session logging выглядел как поломка seq, хотя это просто смена процесса.

### Non-blocking warnings

- optional imports (`qdarktheme`, `bottleneck`, `cuda`, `openpyxl.tests`) зафиксированы как missing, но не объясняют crash-path;
- `road_width_m` отсутствует/некорректен в `meta_json.geometry`, поэтому Animator уходит в derived width warning;
- это отдельный meta/export backlog, но не первопричина аварии Desktop Animator в данном bundle.

## Итог

Главный практический вывод из bundle:
- **чинить надо не solver/export, а Windows GL detached-layout policy**;
- 3D GL окно нельзя насильно переводить в floating detached window на этом runtime/driver path;
- strict-loglint должен различать seq хотя бы по `session_id + pid`.
