# -*- coding: utf-8 -*-
"""model_pneumo_v10_mech_doublewishbone_worldroad_iso6358.py

ВНИМАНИЕ: это *совместимый shim* (переадресация) для UI/паспортов.

В некоторых сборках паспорт компонентов (component_passport.json) ссылается на
модель v10 `model_pneumo_v10_mech_doublewishbone_worldroad_iso6358.py`, но файл
мог отсутствовать. Это вызывало путаницу и потенциальные ошибки при загрузке.

Пока полноценная v10 с ISO 6358 не выделена в отдельный модуль, мы
переиспользуем рабочую v9-модель `model_pneumo_v9_mech_doublewishbone_worldroad.py`.

Никакая функциональность v9 не теряется; v10 будет развита отдельно.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Импортируем реализацию из v9
from model_pneumo_v9_mech_doublewishbone_worldroad import *  # noqa: F401,F403

# Доп. метка версии (не обязательна, но полезна для отчётов)
V10_SHIM = True

