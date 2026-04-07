from pathlib import Path


def test_desktop_animator_uses_face_cache_instead_of_rebuilding_faces_each_frame() -> None:
    txt = Path('pneumo_solver_ui/desktop_animator/app.py').read_text(encoding='utf-8')
    assert 'build_faces=False' in txt
