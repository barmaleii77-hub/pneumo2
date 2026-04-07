from pathlib import Path


def test_launcher_has_shared_venv_recovery_gate() -> None:
    src = Path(__file__).resolve().parents[1] / 'START_PNEUMO_APP.py'
    text = src.read_text(encoding='utf-8', errors='replace')
    assert 'ensure_venv(force_recreate=True)' in text
    assert 'requirements metadata says OK, but import smoke failed' in text
    assert '__smoke_check_runner__' in text


def test_launcher_missing_imports_after_install_are_hard_fail() -> None:
    src = Path(__file__).resolve().parents[1] / 'START_PNEUMO_APP.py'
    text = src.read_text(encoding='utf-8', errors='replace')
    assert 'Запуск продолжать нельзя: окружение неполное или повреждено.' in text
    assert '_safe_messagebox_error("Ошибка зависимостей", msg)' in text
    assert 'return False' in text
