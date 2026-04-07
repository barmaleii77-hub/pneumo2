# TODO / Wishlist addendum — R31W

Дата: 2026-03-24

## Закрыто этим патчем
- Формализован explicit cylinder packaging contract в `meta.geometry`.
- Возвращены честные 3D cylinders/rods/pistons по `solver-points + packaging contract`.
- Убрана invented piston thickness; piston теперь строится как contract-derived disc plane.
- Registry / contract docs синхронизированы с этим слоем.

## Остаётся открытым
- Подтвердить живым Windows SEND bundle, что `R31W` показывает cylinders/rods/pistons стабильно и без новой GL/FPS регрессии.
- Перейти к catalogue-aware Camozzi sizing, outer envelope и clearance contract без нарушения ABSOLUTE LAW.
