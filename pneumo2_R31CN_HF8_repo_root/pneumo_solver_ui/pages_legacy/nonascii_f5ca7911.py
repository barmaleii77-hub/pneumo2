# ORIGINAL_FILENAME: 98_╨í╨▒╨╛╤Ç╨║╨░_╨░╤Ç╤à╨╕╨▓╨░_ZIP.py
# -*- coding: utf-8 -*-
"""Legacy wrapper for the canonical Send Bundle ZIP page."""

from __future__ import annotations

import runpy
from pathlib import Path


CANONICAL_PAGE = Path(__file__).resolve().parents[1] / "pages" / "98_BuildBundle_ZIP.py"

runpy.run_path(str(CANONICAL_PAGE), run_name="__main__")
