# Mech Energy Regression Report

- generated_at: `20260411_172859`
- model: `model_pneumo_v8_energy_audit_vacuum_patched_smooth_all`
- params: `default_base.json`
- suite: `default_suite.json`
- t_end_cap: `1.2` s, dt_min: `0.003` s
- thresholds: rel_th=0.25, pdv_th=0.005 W

_No tests found in suite._

## Notes
- `max_rel_err_E` and `end_rel_err_E` относятся к проверке баланса механической энергии.
- `max_pdv_err_W` — проверка p·dV (gauge) против F*ṡ по цилиндрам.
- Для строгого режима используйте `--strict` (rc=2 при провале порогов).
