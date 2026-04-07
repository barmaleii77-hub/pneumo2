# RELEASE BUILD REPORT R31AL (2026-03-26)

## Основание
- base source: `PneumoApp_v6_80_R176_R31AK_2026-03-26`
- new release: `PneumoApp_v6_80_R176_R31AL_2026-03-26`
- primary audit bundle: `e7b024e2-62e7-4318-b4a8-d109008cc7f7.zip`

## Ключевые выводы аудита
- `anim_latest` в bundle уже был densified и не выглядел главным bottleneck для playback;
- главный speed/perf bottleneck сместился в Desktop Animator GUI-thread policy: 4 ms service timer + source-frame chasing + слишком дорогие auxiliary panes;
- browser idle CPU нельзя было честно считать закрытым, пока оставались timeout-polling loops;
- цилиндры читались плохо из-за оболочки без выраженных торцевых стенок и слишком сильной внутренней камеры.

## Реальные изменения
- `desktop_animator/app.py`: continuous-time playhead, display-rate timer, более жёсткая demotion auxiliary panes, без hide/show live GL в layout transition, capped cylinder mesh.
- `components/*` + `app.py` + `pneumo_ui_app.py`: удалён long-idle polling path, добавлены wake hooks через `scroll/resize` в дополнение к `storage/focus/visibility`.
- `docs/11_TODO.md`, `docs/12_Wishlist.md`, `docs/WISHLIST.json`: добавлен R31AL backlog/context addendum.
- новые тесты: `test_r51_animator_display_rate_and_idle_stop.py`, `test_r51_cylinder_caps_and_visual_cleanup.py`.

## Верификация
- `py_compile`: PASS
- `compileall -q pneumo_solver_ui tests`: PASS
- targeted pytest slice: PASS
- JS syntax recheck for modified HTML components: PASS

## Итог
R31AL — это corrective release по глубинной модели работы Animator и browser idle path. Он не обещает магически закрыть весь perf track без живой Windows проверки, но переводит проект с неправильного направления («ещё увеличить sleep») на корректное: display-rate playback, stop-idle loops и реальное упрощение периферийной графики.
