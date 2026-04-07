# TODO / WISHLIST addendum R31O (2026-03-23)

## Закрыто этим шагом

- [x] **RING-RAW-08:** raw `zL_m/zR_m` больше не подменяются seam-closure коррекцией; preview/summary видят authored truth, а periodic spline строится отдельно.
- [x] **RING-SLOPE-09:** для уже периодического SINE с фазой убрана ложная seam slope mismatch коррекция, раздувавшая амплитуду у конца круга.
- [x] **UI-COMPAT-10:** из активного ring UI убран оставшийся deprecated `use_container_width`.

## Остаётся открытым

- [ ] **WEB-PERF-05b:** measured browser Performance trace на Windows (CPU/FPS/idle after solve).
- [ ] **SOLVER-PTS-06:** добить solver-points completeness для полностью честной подвесочной геометрии.
- [ ] **CYL-PACK-11:** финализировать packaging contract цилиндров/штоков/поршней, чтобы честно вернуть 3D тела без фантазии.
- [ ] **WIN-ACCEPT-12:** повторно принять bundle на реальном Windows Qt/OpenGL viewport: playback/FPS/road/contact acceptance.

## Практический смысл

После R31O:
- raw ring preview больше не врёт о локальной амплитуде из-за seam-коррекции;
- periodic ring export остаётся доступным через closed spline path;
- активный Streamlit runtime чище по width API;
- TODO/WISHLIST теперь лучше отделяют закрытый code-fix от незакрытого release-gate.
