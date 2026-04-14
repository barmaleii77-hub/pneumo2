from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_defaults import (
    canonical_base_json_path,
    canonical_model_path,
    canonical_ranges_json_path,
    canonical_suite_json_path,
    canonical_worker_path,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_r31ax_canonical_optimization_paths_exist() -> None:
    ui_root = _repo_root() / "pneumo_solver_ui"
    for path in (
        canonical_model_path(ui_root),
        canonical_worker_path(ui_root),
        canonical_base_json_path(ui_root),
        canonical_ranges_json_path(ui_root),
        canonical_suite_json_path(ui_root),
    ):
        assert path.exists(), str(path)


def test_r31ax_ui_apps_define_oneclick_defaults_from_canonical_helpers() -> None:
    for rel_path in ("pneumo_solver_ui/app.py", "pneumo_solver_ui/pneumo_ui_app.py"):
        src = (_repo_root() / rel_path).read_text(encoding="utf-8")
        assert 'MODEL_DEFAULT = str(canonical_model_path(HERE))' in src
        assert 'WORKER_DEFAULT = str(canonical_worker_path(HERE))' in src
        assert 'SUITE_DEFAULT = str(canonical_suite_json_path(HERE))' in src
        assert 'BASE_DEFAULT = str(canonical_base_json_path(HERE))' in src
        assert 'RANGES_DEFAULT = str(canonical_ranges_json_path(HERE))' in src
        for token in (
            'os.path.basename(MODEL_DEFAULT)',
            'os.path.basename(WORKER_DEFAULT)',
            'os.path.basename(SUITE_DEFAULT)',
            'os.path.basename(BASE_DEFAULT)',
            'os.path.basename(RANGES_DEFAULT)',
        ):
            assert token in src


def test_r31ax_root_app_defines_string_key_registry() -> None:
    src = (_repo_root() / 'pneumo_solver_ui' / 'app.py').read_text(encoding='utf-8')
    assert 'BASE_STR_KEYS = {k for k, v in base0.items() if isinstance(v, str)}' in src
    assert 'str_keys_ui = [k for k in BASE_STR_KEYS if (k in base0)]' in src


def test_r31ax_bootstrap_demotes_optional_missing_modules_from_error_spam() -> None:
    src = (_repo_root() / 'pneumo_solver_ui' / 'diag' / 'bootstrap.py').read_text(encoding='utf-8')
    assert 'OptionalModuleMissing' in src
    for name in [
        'CoolProp',
        'cython',
        'scikits',
        'sksparse',
        'uarray',
        'xarray',
        'fqdn',
        'rfc3987',
        'rfc3986_validator',
        'rfc3987_syntax',
        'rfc3339_validator',
        'webcolors',
        'jsonpointer',
        'uri_template',
        'isoduration',
        'anywidget',
    ]:
        assert f'"{name}"' in src
