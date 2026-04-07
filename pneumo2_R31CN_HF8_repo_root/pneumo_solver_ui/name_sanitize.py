from __future__ import annotations

import hashlib
import re
from typing import Final

_WINDOWS_RESERVED_BASENAMES: Final[set[str]] = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}
_INVALID_WIN_CHARS_RE: Final[re.Pattern[str]] = re.compile(r'[<>:"/\|?*\x00-\x1f]+')
_MULTI_UNDERSCORE_RE: Final[re.Pattern[str]] = re.compile(r'_+')


def _guard_windows_basename(name: str, *, default: str) -> str:
    base = (name or default).strip()
    stem = base.split('.', 1)[0].rstrip(' .').upper()
    if stem in _WINDOWS_RESERVED_BASENAMES:
        base = f'_{base}'
    base = base.rstrip(' .')
    return base or default


def sanitize_ascii_id(s: str, max_len: int = 80, *, default: str = 'item') -> str:
    """Return a filesystem-friendly ASCII id for filenames and cache dirs.

    Keeps only latin letters, digits, dots, underscores and dashes. Also guards
    against Windows reserved basenames such as ``CON`` or ``LPT1``.
    """
    s = str(s or '').strip()
    s = _INVALID_WIN_CHARS_RE.sub('_', s)
    s = re.sub(r'\s+', '_', s, flags=re.UNICODE)
    s = re.sub(r'[^0-9A-Za-z._-]+', '_', s)
    s = _MULTI_UNDERSCORE_RE.sub('_', s).strip(' ._-')
    if not s:
        s = default
    s = _guard_windows_basename(s, default=default)
    return s[:max_len] or default


def sanitize_unicode_id(s: str, max_len: int = 80, *, default: str = 'run') -> str:
    """Return a Windows-safe id while preserving readable Unicode word chars.

    Windows supports Unicode paths, so we keep letters/digits from user names
    (including Cyrillic) and only remove path-hostile characters and control
    chars. Reserved basenames are prefixed with ``_``.
    """
    s = str(s or '').strip()
    s = _INVALID_WIN_CHARS_RE.sub('_', s)
    s = re.sub(r'\s+', '_', s, flags=re.UNICODE)
    s = re.sub(r'[^\w.-]+', '_', s, flags=re.UNICODE)
    s = _MULTI_UNDERSCORE_RE.sub('_', s).strip(' ._-')
    if not s:
        s = default
    s = _guard_windows_basename(s, default=default)
    return s[:max_len] or default


def _stable_obj_hash(obj: object) -> str:
    return hashlib.sha1(str(obj).encode('utf-8')).hexdigest()[:12]


def sanitize_test_name(name: str, max_len: int = 80) -> str:
    """Filesystem-friendly test name with collision-resistant hash suffix."""
    s = str(name or '').strip()
    if not s:
        return 'test_' + _stable_obj_hash('test')

    safe = sanitize_unicode_id(s, max_len=max_len, default='test')
    h = _stable_obj_hash(s)
    keep = max(1, max_len - (1 + len(h)))
    if len(safe) > keep:
        safe = safe[:keep].rstrip(' ._-') or 'test'
    safe = _guard_windows_basename(safe, default='test')
    return f'{safe}_{h}'


# Backward-friendly public alias for run/output names.
sanitize_id = sanitize_unicode_id
