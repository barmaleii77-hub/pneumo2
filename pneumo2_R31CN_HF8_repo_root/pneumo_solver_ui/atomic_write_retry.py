from __future__ import annotations

"""Best-effort atomic text/JSON writes with Windows lock retry.

Why this exists:
- UI progress/status files are polled live by other processes.
- On Windows, ``os.replace`` / ``Path.replace`` can fail with sharing violations
  when the destination file is briefly open for reading by another process.
- Progress updates must not crash long-running optimization processes merely
  because a JSON file was momentarily locked by the UI/Explorer/AV.

Policy:
- keep the primary write path atomic (tmp file + replace);
- retry transient sharing violations for a short bounded window;
- never raise on persistent lock for progress-like files: return ``False`` and
  leave the previous payload intact.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_RETRYABLE_WINERRORS = {5, 32}
_RETRYABLE_ERRNOS = {13, 16}


def _is_retryable_replace_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    winerror = int(getattr(exc, 'winerror', 0) or 0)
    errno = int(getattr(exc, 'errno', 0) or 0)
    return (winerror in _RETRYABLE_WINERRORS) or (errno in _RETRYABLE_ERRNOS)


def atomic_write_text_retry(
    path: str | Path,
    text: str,
    *,
    encoding: str = 'utf-8',
    max_wait_sec: float = 3.0,
    retry_sleep_sec: float = 0.05,
    label: str = 'atomic-write',
) -> bool:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = f"{os.getpid()}_{int(time.time_ns())}"
    tmp = target.with_name(f".{target.name}.{stamp}.tmp")
    tmp.write_text(text, encoding=encoding)
    deadline = float(time.time()) + max(0.0, float(max_wait_sec))
    last_exc: BaseException | None = None
    while True:
        try:
            os.replace(str(tmp), str(target))
            return True
        except BaseException as exc:  # best-effort progress/status write path
            last_exc = exc
            if (not _is_retryable_replace_error(exc)) or (float(time.time()) >= deadline):
                break
            time.sleep(max(0.0, float(retry_sleep_sec)))
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass
    try:
        sys.stderr.write(
            f"[{label}] atomic replace failed for {target}: {last_exc!r}\n"
        )
    except Exception:
        pass
    return False


def atomic_write_json_retry(
    path: str | Path,
    payload: Any,
    *,
    ensure_ascii: bool = False,
    indent: int = 2,
    encoding: str = 'utf-8',
    max_wait_sec: float = 3.0,
    retry_sleep_sec: float = 0.05,
    label: str = 'atomic-json',
) -> bool:
    text = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent)
    return atomic_write_text_retry(
        path,
        text,
        encoding=encoding,
        max_wait_sec=max_wait_sec,
        retry_sleep_sec=retry_sleep_sec,
        label=label,
    )


__all__ = [
    'atomic_write_text_retry',
    'atomic_write_json_retry',
]
