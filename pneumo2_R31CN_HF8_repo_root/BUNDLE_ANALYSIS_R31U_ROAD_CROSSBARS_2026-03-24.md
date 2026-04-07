# Bundle analysis — road cross-bars on R31U

Дата: 2026-03-24  
Исходный bundle: `0d5b8236-0226-4996-9f66-e21deaa1c731.zip`  
Релиз в bundle: `PneumoApp_v6_80_R176_R31U_2026-03-24`

## Что подтвердилось

Проблема с поперечными полосами была не в FPS и не в road mesh как таковом.

В `R31U` видимые cross-bars строились так:
1. вычислялись world-anchored целевые позиции полос по `s`;
2. затем каждая полоса **привязывалась к ближайшей строке текущего road mesh** (`nearest-row snapping`);
3. поверх этого оставался **forced terminal bar** на последней видимой строке viewport-а.

Из-за этого появлялись два артефакта:
- мелкое дрожание / ступенчатость полос при сдвиге окна playback;
- лишняя полоса на дальнем краю окна, которая была привязана не к миру, а к текущему viewport edge.

## Метрики (репрезентативный 1280×720 playback viewport)

- nominal visible length: `64.777778 м`
- stable cross spacing: `0.900 м`
- max spatial error от nearest-row snapping: `0.053502 м`
- mean abs spatial error: `0.023386 м`
- mean offset forced edge bar от последней реальной world-полосы: `0.338543 м`
- max offset forced edge bar: `0.900000 м`
- mean temporal jitter у центральной полосы: `0.034761 м`
- max temporal jitter у центральной полосы: `0.097891 м`

## Исправление в R31V

- forced viewport-edge terminal bar удалён;
- поперечные полосы теперь строятся по **точным world-anchored `s_targets`**;
- геометрия каждой полосы берётся прямой интерполяцией текущих `x/y/z_left/z_center/z_right/normal`, а не по ближайшей строке road mesh;
- продольные rails продолжают использовать существующий dense road mesh.

## Ожидаемый эффект

- убирается мелкое дрожание/ступенчатость полос;
- исчезает странная крайняя полоса, плывущая вместе с границей окна;
- road surface mesh и contact patch path остаются без изменений.
