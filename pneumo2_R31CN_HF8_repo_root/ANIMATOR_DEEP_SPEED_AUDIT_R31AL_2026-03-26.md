# ANIMATOR DEEP SPEED AUDIT R31AL (2026-03-26)

## Что показал свежий bundle

- `anim_latest` уже **не выглядит недосэмплированным**: 2764 кадров за 15.000 с, медианный шаг времени 5.43 мс, максимальный шаг по пути около 0.083 м/кадр.
- Значит после R31AK bottleneck сместился с плотности кадров на **Desktop Animator playback/runtime policy** и общую конкуренцию за GUI thread.
- По `AnimatorAuxCadence` в bundle видны окна с 14 видимыми auxiliary panes; медианная частота обновления logged panes около 0.346 Hz. Это подтверждает, что периферия продолжает участвовать в budget, хотя пользы во время playback почти не добавляет.

## Root cause, который дал R31AL

1. В R31AK playback всё ещё зависел от **source-frame chasing** и очень частого GUI timer path. Под нагрузкой это схлопывало разные speed settings в один «дёрганый» режим и создавало ложное ощущение, что сама анимация «слишком простая, но почему-то тяжёлая».
2. Auxiliary panes всё ещё обновлялись слишком близко к live 3D: fast-group содержал не только HUD, а вместе с ним ещё и front/rear/left/right views.
3. В Web UI оставались компоненты, где idle CPU держался не математикой, а `timeout`-wake loops. Простое растягивание sleep уже три раза не доказало эффекта, поэтому R31AL добивает именно **остановку loop**, а не очередную задержку.
4. Визуализация цилиндров читалась плохо: прозрачная оболочка без читаемых торцов плюс слишком доминирующая внутренняя камера создавали ощущение «внутри ещё один цилиндр».

## Что поменяно в R31AL

### Desktop Animator
- Playback переведён на **continuous-time playhead**: GUI thread выбирает ближайший кадр к текущему времени проигрывания, а не пытается догонять каждый исходный source frame.
- Таймер playback переведён с 4 ms service semantics на **display-rate policy** (`16/12/8/6 ms` по speed buckets).
- `front/rear/left/right` и прочая периферия выведены из fast lane; fast-group оставлен только для HUD.
- Auxiliary FPS budgets дополнительно сжаты до `10/3/6/1.5` и порог many-visible опущен до `6`.
- Во время GL layout transition больше не используется `hide()/show()` у live GL view; это убирает один из тяжёлых и нестабильных путей.

### Web UI idle CPU
- Для follower/embedded widgets удалён старый `__nextIdleMs(60000, 180000, 300000)` polling path.
- В idle loops теперь **останавливаются**, а не продолжают жить на timeout. Wake идёт главным образом через `storage / focus / visibility / scroll / resize`.
- В проверенном наборе файлов старый long-idle polling встречался в 11 местах до патча и в 0 местах после патча.

### Cylinder visuals
- Actuator meshes переведены на **capped cylinder geometry** с торцевыми стенками.
- Outer housing теперь рисуется гранями, а не только рёбрами; внутренняя камера сделана слабее и больше не должна доминировать сверху как «второй цилиндр».

## Что ещё честно НЕ считается доказанным

- Bundle не содержит полноценного browser perf trace, поэтому post-run Web UI CPU tail по Windows всё ещё требует свежего SEND bundle для окончательной приёмки.
- Если на следующем bundle drag/resize 3D всё ещё будет ломать responsiveness, следующий шаг уже должен быть не pause-only, а **полное recreate GL viewport/context после layout transition**.
