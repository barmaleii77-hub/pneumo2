# TODO / Wishlist addendum — R31Q (2026-03-24)

## Что исправлено в проектном статусе

- Статус R31P скорректирован: это был workaround с отключением требуемого detached 3D режима, а не принятый root-cause fix.
- В R31Q live 3D GL переведён на dedicated top-level window (`ExternalPanelWindow`) вместо floating `QDockWidget`.
- Сохранены требования пользователя: 3D окно остаётся отдельным, movable, resizable и toggleable.
- Добавлены persistence geometry/visible и корректное закрытие внешнего 3D окна вместе с главным Animator окном.

## Что остаётся открытым

- Windows retest уже на R31Q с новым SEND-bundle.
- Canonical `road_width_m` в export/meta.
- Measured Windows/browser performance acceptance.
- Solver-points completeness и cylinder packaging contract.
