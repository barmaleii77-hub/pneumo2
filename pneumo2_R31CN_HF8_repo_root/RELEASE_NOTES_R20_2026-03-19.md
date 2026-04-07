# Release Notes — R20

Release: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R20_2026-03-19`

## Что исправлено
- Исправлен корень проблемы с рычагами в animator для фактически используемой модели `model_pneumo_v9_doublewishbone_camozzi.py`.
- В solver/export добавлены explicit trapezoid branch points для верхнего и нижнего рычагов.
- По умолчанию оба цилиндра крепятся к верхнему рычагу, а `Ц1/Ц2` разнесены по продольной оси относительно оси ступицы.
- Источник данных (`default_base.json`) теперь явно задаёт X-координаты ветвей трапеций и X-смещения верхних шарниров цилиндров.
- Сохранены web hotfix-поправки R19.

## Чего этот релиз не делает
- Не вводит выдуманные full 3D hardpoints из воздуха.
- Не меняет физику reduced-DW solver beyond explicit source-data defaults/export contract for visualization.
