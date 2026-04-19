from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_tick_redraws_live_frame_once_per_playback_service_tick() -> None:
    assert APP.count('self._update_frame(int(self._idx), sample_t=self._play_cursor_t_s)') == 1


def test_animator_source_lifts_contact_patch_above_road_to_avoid_z_fighting() -> None:
    assert 'patch_verts[:, 2] = np.asarray(patch_verts[:, 2], dtype=float) + max(0.0015, 0.008 * wheel_radius_m)' in APP


def test_animator_source_uses_axis_sidewall_bulge_and_wishbone_plate_mesh() -> None:
    assert "def _wishbone_plate_mesh(" in APP
    assert 'verts[:, 1] = np.asarray(verts[:, 1], dtype=float) + (side_sign * sidewall_bulge_m)' in APP


def test_animator_user_facing_file_actions_do_not_expose_internal_animation_pointer() -> None:
    operator_text = (
        ROOT / "pneumo_solver_ui" / "desktop_animator" / "operator_text.py"
    ).read_text(encoding="utf-8")
    main_src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "main.py").read_text(
        encoding="utf-8"
    )
    visible_text = "\n".join([APP, operator_text, main_src])

    assert "Загрузить файл анимации" in APP
    assert "Автообновлять файл анимации" in APP
    assert "Файлы анимации (*.npz)" in APP
    assert "не выбран файл анимации" in operator_text
    assert "Автоматически загружать последний файл анимации" in main_src

    forbidden_visible_phrases = (
        "Следить за anim_latest",
        "Слежение за anim_latest",
        "Слежение недоступно",
        "Открыть NPZ",
        "NPZ files",
        "артефакт анимации",
        "указатель anim_latest",
        "NPZ-файл не найден",
        "контракта перехода",
        "контракт перехода",
        "JSON-указателю anim_latest",
        "указателем anim_latest",
        "HO-008: Контекст анализа",
        "Контекст анализа",
        "контекст анализа HO-008",
        "analysis_context.json не найден",
        "вне HO-008",
        "Не удалось загрузить NPZ",
        "самопроверок=",
    )
    for phrase in forbidden_visible_phrases:
        assert phrase not in visible_text
