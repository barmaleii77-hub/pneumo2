# Release Summary — R20

База: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R19_2026-03-19` + geometry hotfix for arms/cylinders in the actually loaded camozzi model.

## Что изменено
- `model_pneumo_v9_doublewishbone_camozzi.py`: теперь пробрасывает explicit branch/top-X source-data в `append_solver_points_full_dw2d`.
- `solver_points_geometry.py`: экспортирует trapezoid branch hardpoints и разнесённые цилиндры по X, с явным выбором рычага/ветви.
- `desktop_animator/app.py`: использует quad/hardpoint solver-points для рисования трапеций рычагов, а не только центральные линии.
- `default_base.json`: добавлены explicit geometry defaults для ветвей трапеций и X-разноса цилиндров; обе ветви цилиндров по умолчанию на верхнем рычаге.
- `default_ranges.json`, `01_PARAMETER_REGISTRY.md`, `DATA_CONTRACT_UNIFIED_KEYS.md`: добавлены ключи R20 geometry hotfix.

## Проверка на коротком camozzi run
- `arm_pivot_ЛП_y_м = 0.150000`
- `arm_joint_ЛП_y_м = 0.500000`
- `cyl1_top_ЛП_x_м = 0.790000`
- `cyl2_top_ЛП_x_м = 0.710000`
- `cyl1_bot_ЛП_x_м = 0.802000`
- `cyl2_bot_ЛП_x_м = 0.698000`
- `upper_arm_frame_front_ЛП_x_м = 0.830000`
- `upper_arm_frame_rear_ЛП_x_м = 0.670000`
- `lower_arm_frame_front_ЛП_x_м = 0.830000`
- `lower_arm_frame_rear_ЛП_x_м = 0.670000`

Ожидаемый эффект: в animator оба рычага видны как трапеции с передней/задней ветвями; `Ц1` и `Ц2` больше не совпадают по X и оба по умолчанию сидят на верхнем рычаге.
