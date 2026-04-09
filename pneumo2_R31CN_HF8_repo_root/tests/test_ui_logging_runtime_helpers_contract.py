from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from pneumo_solver_ui.ui_logging_runtime_helpers import (
    configure_runtime_ui_logger,
    ensure_runtime_file_logger,
    prepare_runtime_log_dir,
    publish_session_callback,
)


def test_prepare_runtime_log_dir_returns_created_path(tmp_path: Path) -> None:
    log_dir = tmp_path / "nested" / "logs"

    resolved = prepare_runtime_log_dir(log_dir)

    assert resolved == log_dir
    assert log_dir.is_dir()


def test_publish_session_callback_writes_callable() -> None:
    session_state: dict[str, object] = {}
    callback = lambda: None

    ok = publish_session_callback(session_state, "_log_event_cb", callback)

    assert ok is True
    assert session_state["_log_event_cb"] is callback


def test_configure_runtime_ui_logger_disables_propagation() -> None:
    logger = configure_runtime_ui_logger("test.ui_logging_runtime.bootstrap")

    assert logger.name == "test.ui_logging_runtime.bootstrap"
    assert logger.level == logging.INFO
    assert logger.propagate is False


def test_ensure_runtime_file_logger_uses_env_run_id_and_session_started(
    tmp_path: Path,
    monkeypatch,
) -> None:
    logger = logging.getLogger("test.ui_logging_runtime.env")
    logger.handlers[:] = []
    session_state: dict[str, object] = {}
    monkeypatch.setenv("PNEUMO_RUN_ID", "RUN-42")

    log_path = ensure_runtime_file_logger(
        session_state,
        logger=logger,
        log_dir=tmp_path,
        prefer_env_run_id=True,
        set_session_started=True,
        time_fn=lambda: 123.5,
    )

    assert session_state["_session_id"] == "RUN-42"
    assert session_state["_session_started"] == 123.5
    assert log_path == str((tmp_path / "ui_RUN-42.log").resolve())
    assert any(getattr(handler, "baseFilename", None) == log_path for handler in logger.handlers)

    for handler in list(logger.handlers):
        try:
            handler.close()
        finally:
            logger.removeHandler(handler)


def test_ensure_runtime_file_logger_reuses_existing_handler(tmp_path: Path) -> None:
    logger = logging.getLogger("test.ui_logging_runtime.reuse")
    logger.handlers[:] = []
    session_state: dict[str, object] = {}

    first = ensure_runtime_file_logger(
        session_state,
        logger=logger,
        log_dir=tmp_path,
        now_fn=lambda: datetime(2026, 4, 9, 10, 11, 12),
    )
    second = ensure_runtime_file_logger(
        session_state,
        logger=logger,
        log_dir=tmp_path,
    )

    assert first == second
    assert session_state["_session_id"] == "20260409_101112_pid{}".format(__import__("os").getpid())
    assert len(logger.handlers) == 1

    for handler in list(logger.handlers):
        try:
            handler.close()
        finally:
            logger.removeHandler(handler)


def test_runtime_logging_helpers_are_wired_into_active_entrypoints() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    helper_source = (
        repo_root / "pneumo_solver_ui" / "ui_logging_runtime_helpers.py"
    ).read_text(encoding="utf-8")
    app_source = (repo_root / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (repo_root / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def ensure_runtime_file_logger" in helper_source
    assert "def prepare_runtime_log_dir" in helper_source
    assert "def configure_runtime_ui_logger" in helper_source
    assert "def publish_session_callback" in helper_source
    assert "from pneumo_solver_ui.ui_logging_runtime_helpers import (" in app_source
    assert "from pneumo_solver_ui.ui_logging_runtime_helpers import (" in heavy_source
    assert "prepare_runtime_log_dir(" in app_source
    assert "prepare_runtime_log_dir(" in heavy_source
    assert "configure_runtime_ui_logger(" in app_source
    assert "configure_runtime_ui_logger(" in heavy_source
    assert "publish_session_callback(" in app_source
    assert "publish_session_callback(" in heavy_source
    assert "ensure_runtime_file_logger(" in app_source
    assert "ensure_runtime_file_logger(" in heavy_source
    assert "def _init_file_logger_once(" not in app_source
    assert "def _init_file_logger_once(" not in heavy_source
    assert "LOG_DIR.mkdir(" not in app_source
    assert "LOG_DIR.mkdir(" not in heavy_source
    assert '_APP_LOGGER = logging.getLogger("pneumo_ui")' not in app_source
    assert '_APP_LOGGER = logging.getLogger("pneumo_ui")' not in heavy_source
    assert 'st.session_state["_log_event_cb"] = log_event' not in app_source
    assert 'st.session_state["_log_event_cb"] = log_event' not in heavy_source
    assert "from logging.handlers import RotatingFileHandler" not in app_source
    assert "from logging.handlers import RotatingFileHandler" not in heavy_source
