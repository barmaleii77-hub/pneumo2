# Cylinder stroke/body diagnostics — R31AG (2026-03-25)

## Источник данных по умолчанию
Из `pneumo_solver_ui/default_base.json`:

### Ц1
- bore diameter: `0.032000000 m`
- rod diameter: `0.016000000 m`
- wall thickness: `0.003000000 m`
- outer diameter: `0.038000000 m`
- max stroke front/rear: `0.250000000 / 0.250000000 m`
- dead volume height: `0.018650970 m`
- body length front/rear: `0.293301940 / 0.293301940 m`

### Ц2
- bore diameter: `0.050000000 m`
- rod diameter: `0.014000000 m`
- wall thickness: `0.003000000 m`
- outer diameter: `0.056000000 m`
- max stroke front/rear: `0.250000000 / 0.250000000 m`
- dead volume height: `0.007639437 m`
- body length front/rear: `0.271278875 / 0.271278875 m`

## Как это обрабатывает solver
- Solver читает `ход_штока_Ц1_*` / `ход_штока_Ц2_*` как максимальные ходы.
- В `model_pneumo_v9_doublewishbone_camozzi.py` позиция штока задаётся как `s_raw = s0 - delta_rod`, затем клипуется в `[0, L_stroke]`.
- Комментарий в solver: `s уменьшается при сжатии подвески (delta_rod>0)`.

## Как это теперь обрабатывает animator
- Animator использует fixed cylinder body length по формуле: `stroke + 2*dead_height + 2*wall_thickness`.
- `top` остаётся frame/body-side mount, `bot` — arm/rod-side mount.
- При росте `stroke_pos` piston plane движется к rod/arm side внутри fixed body shell.
- `housing_seg` больше не рисуется как full pin-to-pin shell; теперь это fixed external body shell.
- Exposed rod рисуется отдельно от fixed body shell.

## Web UI CPU root cause (текущая гипотеза, уже адресованная в коде)
- Проблема не в одном только idle timeout, а в том, что тяжёлые web renderers продолжали держать loop-схему живой даже в idle.
- В R31AG тяжёлые компоненты переведены на full idle stop + event-driven wake (render/storage/focus/visibility/user actions).
