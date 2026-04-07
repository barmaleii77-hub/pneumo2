# PneumoApp_v6_80_R176_WINDOWS_CLEAN_R22_2026-03-19

База: R21.

Основные изменения R22:
- исправлено визуальное отвязывание frame-mounted точек рычагов/цилиндров от плоскости рамы;
- worldroad переведён на тот же explicit trapezoid/cylinder contract, что и camozzi;
- добавлена optional visual-геометрия цилиндров (корпус/шток/поршень) через meta.geometry;
- увеличена плотность mesh дороги в Desktop Animator;
- launcher по умолчанию скрывает transient console window.

Важно:
- это переходный фикс на reduced-DW solver;
- old bundles, сгенерированные до R22, могут не содержать новых optional meta.geometry полей цилиндров.
