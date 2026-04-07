# R31A — ring amplitude/summary follow-up (2026-03-22)

База: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R25_2026-03-20_R31_DIAGNOSTICS_WEB_GL_CONTACT_PATCHED`

Исправления этого прохода:

1. **Preview ring**
   - основная локальная метрика переименована в `amplitude A`;
   - `p-p = max-min` теперь явно помечено как `НЕ A`.

2. **Segment summary**
   - длина сегмента теперь считается канонически даже если `length_m` не задан явно;
   - используется тот же принцип, что и в генераторе кольца: `duration_s + speed_kph/v_end_kph`;
   - в summary амплитуда считается как `max(|z-median|)`, а `p-p` остаётся отдельной метрикой.

3. **Scenario export**
   - при сборке `scenario_json` каждому сегменту сериализуется вычисленное `length_m`, чтобы downstream-цепочка не гадала длины заново.

Что не менялось в этом пакете:
- R31 Web CPU / dense road / contact patch / wall-time playback — взято из последнего релиза как база без отката.
