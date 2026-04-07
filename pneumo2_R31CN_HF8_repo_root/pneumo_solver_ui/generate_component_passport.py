# -*- coding: utf-8 -*-
"""generate_component_passport.py

Экспорт "паспорта" расходных параметров компонентов в формате JSON.

Зачем:
- В проекте есть встроенная база Camozzi (VNR и SCO) с паспортными Qn (Nl/min, ANR).
- Для режима расчёта расхода по ISO 6358 (passive_flow_model='iso6358')
  удобнее иметь эквивалентные параметры ISO: C, b, m, а для check‑клапанов ещё и Δpc.

Что делает скрипт:
- Берёт CAMOZZI_VNR и CAMOZZI_SCO из model_pneumo_v8_energy_audit_vacuum.py
- Конвертирует Qn -> C через C_from_Qn_iso() в одной паспортной точке
  (по умолчанию 6 bar(g), Δp=1 bar).
- Сохраняет JSON, который можно редактировать/версионировать отдельно.

Запуск:
    python generate_component_passport.py

Параметры (опционально):
    --b 0.5 --m 0.5 --beta_lam 0.999 --out component_passport.json

Важно про физику:
- Это НЕ утверждение, что Camozzi даёт ISO‑параметры C,b,m.
  Здесь C подбирается так, чтобы модель ISO в паспортной точке воспроизводила Qn.
- b и m задаются пользователем (по умолчанию берём константы ISO6358_*_DEFAULT из модели).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import model_pneumo_v8_energy_audit_vacuum as model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--b', type=float, default=None, help='ISO 6358 b (critical pressure ratio)')
    ap.add_argument('--m', type=float, default=None, help='ISO 6358 m (subsonic index)')
    ap.add_argument('--beta_lam', type=float, default=None, help='ISO 6358 beta_lam (smoothing near pr->1)')
    ap.add_argument('--out', type=str, default='component_passport.json', help='Output JSON path')
    args = ap.parse_args()

    b = float(args.b) if args.b is not None else float(model.ISO6358_B_DEFAULT)
    m = float(args.m) if args.m is not None else float(model.ISO6358_M_DEFAULT)
    beta_lam = float(args.beta_lam) if args.beta_lam is not None else float(model.ISO6358_BETA_LAM_DEFAULT)

    meta = {
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'anr': {
            'p_Pa': float(model.P_ANR),
            'T_K': float(model.T_ANR),
            'rho_kg_m3': float(model.RHO_ANR),
        },
        'passport_point': {
            'p_up_gauge_bar': 6.0,
            'dp_bar': 1.0,
            'p_up_abs_Pa': float(model.P_ATM + 6e5),
            'p_dn_abs_Pa': float(model.P_ATM + 5e5),
        },
        'iso_assumptions': {
            'b': b,
            'm': m,
            'beta_lam': beta_lam,
            'note': 'C is fitted so that ISO model reproduces Qn at the passport point',
        },
    }

    out = {
        'meta': meta,
        'VNR': {},
        'SCO': {},
    }

    for code, d in model.CAMOZZI_VNR.items():
        Qn = float(d.get('Qn_Nl_min', 0.0))
        dp_open_bar = float(d.get('dp_откр_бар', 0.0))
        C = float(model.C_from_Qn_iso(Qn, b=b, m=m, beta_lam=beta_lam))
        out['VNR'][code] = {
            'Qn_Nl_min': Qn,
            'dp_open_bar': dp_open_bar,
            'iso': {
                'C_m3_s_Pa': C,
                'C_dm3_s_bar': C * 1e8,
                'b': b,
                'm': m,
            }
        }

    for code, d in model.CAMOZZI_SCO.items():
        Qn_open = float(d.get('Qn_open_Nl_min', 0.0))
        Qn_closed = float(d.get('Qn_closed_Nl_min', 0.0))
        dmax_mm = float(d.get('d_max_мм', 0.0))

        C_open = float(model.C_from_Qn_iso(Qn_open, b=b, m=m, beta_lam=beta_lam))
        C_closed = float(model.C_from_Qn_iso(Qn_closed, b=b, m=m, beta_lam=beta_lam))

        out['SCO'][code] = {
            'd_max_mm': dmax_mm,
            'Qn_open_Nl_min': Qn_open,
            'Qn_closed_Nl_min': Qn_closed,
            'iso': {
                'C_open_m3_s_Pa': C_open,
                'C_closed_m3_s_Pa': C_closed,
                'C_open_dm3_s_bar': C_open * 1e8,
                'C_closed_dm3_s_bar': C_closed * 1e8,
                'b': b,
                'm': m,
            }
        }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK: wrote {args.out}")
    print(f"  VNR: {len(out['VNR'])} items")
    print(f"  SCO: {len(out['SCO'])} items")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
