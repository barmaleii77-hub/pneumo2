# -*- coding: utf-8 -*-
"""self_check.py

Быстрые проверки согласованности проекта.

Запуск:
    python self_check.py

Что проверяет:
 1) build_test_suite() понимает типы из default_suite.json (в т.ч. комбо_крен_плюс_микро)
 2) candidate_penalty() реагирует на нарушения по ключевым ограничениям
 3) минимальный прогон модели (короткий тест) возвращает метрики с ожидаемыми ключами
 4) sanity‑проверка эквивалентов ISO 6358‑3 (серия/параллель) в iso6358_system.py
 5) sanity‑проверка учёта dPcrack (cracking pressure) в ISO‑check модели

Скрипт НЕ требует streamlit.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent

# Ensure local-file imports work even when this script is executed via `python -m`.
# Some dynamically-loaded models use fallback `from scheme_integrity import ...`.
# That requires the pneumo_solver_ui directory to be on sys.path.
import sys as _sys
from pneumo_solver_ui.module_loading import load_python_module_from_path
if str(HERE) not in _sys.path:
    _sys.path.insert(0, str(HERE))
if str(HERE.parent) not in _sys.path:
    _sys.path.insert(0, str(HERE.parent))



def main() -> int:
    worker = load_python_module_from_path(HERE / "opt_worker_v3_margins_energy.py", "worker")
    model = load_python_module_from_path(HERE / "model_pneumo_v8_energy_audit_vacuum.py", "model")

    base = json.loads((HERE / "default_base.json").read_text(encoding="utf-8"))
    suite = json.loads((HERE / "default_suite.json").read_text(encoding="utf-8"))

    # --- structured snapshot of WARN/FAIL for UI + reports ---
    warn_items = []  # list[dict]
    fail_items = []  # list[dict]

    def _add(level: str, step: str, message: str, **data):
        item = {"level": level, "step": step, "message": message, "data": data}
        if level == "FAIL":
            fail_items.append(item)
        else:
            warn_items.append(item)

    def _finalize(rc: int) -> int:
        """Write REPORTS/SELF_CHECK_SILENT_WARNINGS.(json|md). Never raises."""
        try:
            rel = ""
            ver = ""
            try:
                from pneumo_solver_ui.release_info import get_release, get_version  # type: ignore

                rel = str(get_release())
                ver = str(get_version())
            except Exception:
                rel = str(os.environ.get("PNEUMO_RELEASE", ""))
                ver = str(os.environ.get("PNEUMO_VERSION", ""))

            report = {
                "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "release": rel,
                "version": ver,
                "rc": int(rc),
                "summary": {
                    "fail_count": len(fail_items),
                    "warn_count": len(warn_items),
                },
                "fails": fail_items,
                "warnings": warn_items,
            }

            from pneumo_solver_ui.diag.silent_warnings_report import write_report  # type: ignore

            write_report(report)
        except Exception as e:
            print(f"[self_check] WARN: cannot write silent-warnings report: {e}")
        return rc

    # --- 1) suite types ---
    tests = worker.build_test_suite({"suite": suite})
    names = [t[0] for t in tests]

    print(f"[1] build_test_suite(): тестов собрано = {len(tests)}")
    if not any("комбо" in n for n in names):
        print("  !! ВНИМАНИЕ: среди тестов нет ни одного с 'комбо' в имени. Проверь default_suite.json")
    else:
        print("  OK: комбо-тест присутствует")

    # --- 2) candidate_penalty mapping ---
    targets = {
        "макс_доля_отрыва": 0.0,
        "мин_запас_до_Pmid_бар": 0.2,
        "мин_Fmin_Н": 50.0,
        "мин_запас_до_пробоя_крен_град": 1.0,
        "мин_запас_до_упора_штока_м": 0.005,
        "лимит_скорости_штока_м_с": 2.0,
    }

    m_bad = {
        "доля_времени_отрыв": 0.25,
        "запас_до_Pmid_бар": 0.0,
        "Fmin_шины_Н": 0.0,
        "запас_до_пробоя_крен_град": 0.0,
        "мин_запас_до_упора_штока_все_м": 0.0,
        "макс_скорость_штока_все_м_с": 3.0,
    }
    m_ok = {
        "доля_времени_отрыв": 0.0,
        "запас_до_Pmid_бар": 0.5,
        "Fmin_шины_Н": 100.0,
        "запас_до_пробоя_крен_град": 5.0,
        "мин_запас_до_упора_штока_все_м": 0.02,
        "макс_скорость_штока_все_м_с": 1.0,
    }

    pen_bad = float(worker.candidate_penalty(m_bad, targets))
    pen_ok = float(worker.candidate_penalty(m_ok, targets))
    print(f"[2] candidate_penalty(): pen_bad={pen_bad:.6g}, pen_ok={pen_ok:.6g}")
    if pen_bad <= 0:
        print("  !! ОШИБКА: pen_bad должен быть > 0 (иначе штраф не реагирует на нарушения)")
        return _finalize(2)
    if abs(pen_ok) > 1e-12:
        print("  !! ВНИМАНИЕ: pen_ok ожидается ~0. Проверь формулы нормировки.")
    else:
        print("  OK: штраф реагирует на нарушения и ~0 при выполнении")

    # --- 3) minimal simulation smoke-test ---
    # Укороченный тест, чтобы быстро проверить, что модель и метрики запускаются.
    test = worker.make_test_roll(t_step=0.05, ay=2.0)
    m = worker.eval_candidate_once(model, base, test, dt=0.01, t_end=0.2)

    required_metrics = [
        "доля_времени_отрыв",
        "Fmin_шины_Н",
        "запас_до_Pmid_бар",
        "запас_до_пробоя_крен_град",
        "мин_запас_до_упора_штока_все_м",
        "макс_скорость_штока_все_м_с",
    ]
    missing = [k for k in required_metrics if k not in m]
    print(f"[3] smoke-test simulate(): метрик={len(m)}")
    if missing:
        print("  !! ОШИБКА: не найдены ожидаемые ключи метрик:")
        for k in missing:
            print("   -", k)
        return _finalize(3)
    print("  OK: ключевые метрики на месте")

    # --- 3b) nist_air thermo sanity (cp(T), gamma(T)) ---
    try:
        th = model.get_air_thermo("nist_air", T_table_min=50.0, T_table_max=2000.0, dT=1.0)
        cp300 = float(th.cp(300.0))
        g300 = float(th.gamma(300.0))
        cp1000 = float(th.cp(1000.0))
        g1000 = float(th.gamma(1000.0))
        print(f"[3b] nist_air cp,gamma: cp300={cp300:.1f} J/kg/K, gamma300={g300:.4f}, cp1000={cp1000:.1f}, gamma1000={g1000:.4f}")
        ok = (980.0 < cp300 < 1030.0) and (1.37 < g300 < 1.41) and (cp1000 > cp300) and (g1000 < g300)
        if not ok:
            print("  !! ВНИМАНИЕ: cp(T)/gamma(T) вне ожидаемых границ — проверь формулу/коэффициенты")
        else:
            print("  OK: cp(T), gamma(T) выглядят разумно")
    except Exception as e:
        print("[3b] !! ВНИМАНИЕ: не удалось проверить nist_air thermo:", e)

    # --- 3c) minimal simulation smoke-test for nist_air mode ---
    base_nist = dict(base)
    base_nist["газ_модель_теплоемкости"] = "nist_air"
    m2 = worker.eval_candidate_once(model, base_nist, test, dt=0.01, t_end=0.2)

    missing2 = [k for k in required_metrics if k not in m2]
    print(f"[3c] smoke-test simulate(nist_air): метрик={len(m2)}")
    if missing2:
        print("  !! ОШИБКА: в nist_air не найдены ключевые метрики:")
        for k in missing2:
            print("   -", k)
        return _finalize(31)
    print("  OK: nist_air режим запускается и отдаёт ключевые метрики")

    # --- 3d) energy/entropy audit sanity (drift & sign) ---
    if 'ошибка_энергии_газа_отн' in m:
        e_rel = float(m['ошибка_энергии_газа_отн'])
        print(f"[3d] energy balance: errE_rel={e_rel:.3e}")
        if e_rel > 1e-3:
            print('  !! ВНИМАНИЕ: относительная ошибка баланса энергии >1e-3 — проверь энерго‑консервативный апдейт u')
            _add('WARN','3d','energy balance: errE_rel > 1e-3', errE_rel=float(e_rel), threshold=1e-3)
        else:
            print('  OK: баланс энергии (газ) в норме')
    else:
        print('[3d] WARNING: нет метрики ошибки баланса энергии (ошибка_энергии_газа_отн)')
        _add('WARN','3d','missing metric: ошибка_энергии_газа_отн')

    if 'энтропия_смешение_Дж_К' in m:
        S_mix = float(m['энтропия_смешение_Дж_К'])
        print(f"[3e] entropy mixing generation: {S_mix:.6g} J/K")
        if S_mix < -1e-9:
            print('  !! ВНИМАНИЕ: энтропия смешения отрицательная — формула/знак некорректны')
            _add('WARN','3e','entropy mixing negative', entropy_mix_J_per_K=float(S_mix), threshold=-1e-9)
        else:
            print('  OK: энтропия смешения неотрицательна')
    else:
        print('[3e] WARNING: нет метрики энтропии смешения (энтропия_генерация_смешение_Дж_К)')
        _add('WARN','3e','missing metric: энтропия_смешение_Дж_К')

    # --- 3f) record_full return length sanity ---
    try:
        out_full = model.simulate(base, test, dt=0.01, t_end=0.05, record_full=True)
        print(f"[3f] record_full simulate(): return_items={len(out_full)}")
        if len(out_full) != 11:
            print('  !! ВНИМАНИЕ: simulate(..., record_full=True) должен возвращать 11 элементов (см. README/worker).')
        else:
            print('  OK: record_full возвращает 11 элементов')
    except Exception as e:
        print('[3f] WARNING: record_full simulate() failed:', e)




    # --- 3g) smoke-test для UI дефолтной модели v9 (dw2d + раздельные штоки Ц1/Ц2) ---
    try:
        model_v9 = load_python_module_from_path(HERE / "model_pneumo_v9_mech_doublewishbone_worldroad.py", "model_v9")
        m_v9 = worker.eval_candidate_once(model_v9, base, test, dt=0.01, t_end=0.2)
        missing_v9 = [k for k in required_metrics if k not in m_v9]
        print(f"[3g] smoke-test v9(dw2d): метрик={len(m_v9)}")
        if missing_v9:
            print("  !! ОШИБКА: v9 модель не отдала ключевые метрики:")
            for k in missing_v9:
                print("   -", k)
            return _finalize(32)
        # Важная проверка интеграции: метрики штока должны учитывать Ц2, если модель отдаёт колонки Ц2.
        if "мин_запас_до_упора_штока_Ц2_все_м" not in m_v9:
            print("  !! ВНИМАНИЕ: не найдена метрика 'мин_запас_до_упора_штока_Ц2_все_м' — возможно, rod_metrics игнорирует Ц2.")
        else:
            print("  OK: rod_metrics для v9 учитывает Ц2")

        # Дополнительный контракт record_full (v9)
        out_full_v9 = model_v9.simulate(base, test, dt=0.01, t_end=0.05, record_full=True)
        print(f"[3g2] record_full v9: return_items={len(out_full_v9)}")
        if len(out_full_v9) != 11:
            print("  !! ОШИБКА: v9 simulate(..., record_full=True) должен возвращать 11 элементов")
            return _finalize(33)
        print("  OK: v9 record_full контракт = 11")

    except Exception as e:
        print("[3g] WARNING: v9 smoke-test failed:", e)

    # --- 4) ISO 6358-3 system equivalence sanity checks ---
    iso_sys = load_python_module_from_path(HERE / "iso6358_system.py", "iso_sys")

    pe = 7.0e5   # Pa abs
    Te = 293.15  # K

    e1 = iso_sys.ISOElement("e1", C=1.0e-8, b=0.3, m=0.5)
    e2 = iso_sys.ISOElement("e2", C=2.0e-8, b=0.3, m=0.5)

    s_eq = iso_sys.series_equivalent_iso(pe, Te, [e1, e2])
    p_eq = iso_sys.parallel_equivalent_iso(pe, Te, [[e1], [e2]])

    print(f"[4] ISO 6358-3 eq: Ceq_series={s_eq.C:.3e}, Ceq_parallel={p_eq.C:.3e}")
    if p_eq.C <= max(e1.C, e2.C) * 0.99:
        print("  !! ВНИМАНИЕ: параллельный Ceq ожидается > каждого C_i (примерная проверка)")
    else:
        print("  OK: параллельный Ceq > каждого C_i")

    if s_eq.C >= min(e1.C, e2.C) * 1.001:
        print("  !! ВНИМАНИЕ: последовательный Ceq ожидается < min(C_i) (примерная проверка)")
    else:
        print("  OK: последовательный Ceq < min(C_i)")

    # --- 5) dPcrack (cracking pressure) in ISO-check model ---
    # Проверяем, что dPcrack действительно «съедает» часть перепада (p_up_eff = p_up - dPcrack),
    # а при dp<=dPcrack расход = 0.
    p1 = 7.0e5
    dp_cr = 2.0e4
    p2_closed = p1 - dp_cr  # dp == dPcrack
    md0 = float(model.mdot_iso6358_check_signed(p1, p2_closed, 1.0e-8, dp_crack=dp_cr, dp_width=0.0))
    if abs(md0) > 1e-12:
        print("  !! ВНИМАНИЕ: при dp==dPcrack расход должен быть ~0 (md0=", md0, ")")
    else:
        print("  OK: mdot(dp==dPcrack)~0")

    p2 = 1.0e5
    C = 1.0e-8
    md_model = float(model.mdot_iso6358_check_signed(p1, p2, C, dp_crack=dp_cr, dp_width=0.0))
    md_ref = float(model.mdot_iso6358(p1 - dp_cr, p2, C))
    rel = abs(md_model - md_ref) / max(1e-12, abs(md_ref))
    print(f"[5] dPcrack check: md_model={md_model:.6g}, md_ref={md_ref:.6g}, rel={rel:.3g}")
    if rel > 1e-6:
        print("  !! ВНИМАНИЕ: mdot_check должен совпадать с mdot_iso(p1-dPcrack, p2) при dp_width=0")
        return _finalize(5)
    print("  OK: dPcrack учитывается как p1_eff=p1-dPcrack (dp_width=0)")



    # --- 6) Camozzi Qn -> ISO C passport assignment in network ---
    # Цель: убедиться, что для рёбер Camozzi (VNR/SCO) в режиме passive_flow_model='iso6358'
    # в Edge.C_iso выставляется C, подобранное по Qn (и сохраняются C_min/C_max для дросселей).
    base_iso = dict(base)
    base_iso['модель_пассивного_расхода'] = 'iso6358'
    base_iso['ISO_auto_C_from_Qn_camozzi'] = True

    nodes, node_index, edges, B = model.build_network_full(base_iso)

    vnr_edges = [e for e in edges if (e.kind == 'check' and isinstance(e.camozzi_код, str) and e.camozzi_код.startswith('VNR-'))]
    sco_edges = [e for e in edges if (e.kind == 'orifice' and isinstance(e.camozzi_код, str) and e.camozzi_код.startswith('SCO'))]

    if not vnr_edges:
        print("[6] WARNING: no VNR edges found")
    if not sco_edges:
        print("[6] WARNING: no SCO edges found")

    # VNR: C_iso должен быть задан и воспроизводить паспортный Qn (в одной точке)
    max_rel_vnr = 0.0
    for e in vnr_edges:
        if e.C_iso is None:
            print(f"  !! [6] VNR edge without C_iso: {e.name} / {e.camozzi_код}")
            return _finalize(6)
        Qn_ref = float(model.CAMOZZI_VNR[e.camozzi_код]['Qn_Nl_min'])
        Qn_back = float(model.Qn_from_C_iso(e.C_iso, b=(e.b_iso or model.ISO6358_B_DEFAULT), m=(e.m_iso or model.ISO6358_M_DEFAULT), beta_lam=base_iso.get('ISO_beta_lam', model.ISO6358_BETA_LAM_DEFAULT)))
        rel = abs(Qn_back - Qn_ref) / max(1e-12, abs(Qn_ref))
        max_rel_vnr = max(max_rel_vnr, rel)
    print(f"[6] VNR passport Qn match (worst relative): {max_rel_vnr:.3e}")

    # SCO: C_iso/C_min/C_max должны быть заданы; C_iso должно соответствовать Qn_eff по alpha
    k_profile = float(base_iso.get('экспонента_профиля_дросселя', 1.0))
    k_sil = float(base_iso.get('коэф_потока_глушителя_2905', 1.0))
    max_rel_sco = 0.0
    for e in sco_edges:
        if e.C_iso is None or e.C_min is None or e.C_max is None:
            print(f"  !! [6] SCO edge missing C fields: {e.name} / {e.camozzi_код}  (C={e.C_iso}, Cmin={e.C_min}, Cmax={e.C_max})")
            return _finalize(6)
        d = model.CAMOZZI_SCO[e.camozzi_код]
        Qn_open = float(d['Qn_open_Nl_min']) * (k_sil if ('+2905' in e.camozzi_код) else 1.0)
        Qn_closed = float(d['Qn_closed_Nl_min']) * (k_sil if ('+2905' in e.camozzi_код) else 1.0)
        alpha = float(e.alpha) if e.alpha is not None else 1.0
        alpha_eff = alpha ** k_profile if k_profile > 0 else alpha
        alpha_eff = max(0.0, min(1.0, alpha_eff))
        Qn_eff = Qn_closed + alpha_eff * (Qn_open - Qn_closed)
        Qn_back = float(model.Qn_from_C_iso(e.C_iso, b=(e.b_iso or model.ISO6358_B_DEFAULT), m=(e.m_iso or model.ISO6358_M_DEFAULT), beta_lam=base_iso.get('ISO_beta_lam', model.ISO6358_BETA_LAM_DEFAULT)))
        rel = abs(Qn_back - Qn_eff) / max(1e-12, abs(Qn_eff))
        max_rel_sco = max(max_rel_sco, rel)
    print(f"[6] SCO passport Qn match (worst relative): {max_rel_sco:.3e}")

    

    # --- 7) component_passport.json is actually used (precedence test) ---
    # Идея проверки:
    #  - делаем ISO_b_default намеренно другим,
    #  - включаем passport,
    #  - убеждаемся, что b_iso/C_iso берутся из паспорта, а не из ISO_b_default.
    passport_file = HERE / "component_passport.json"
    if passport_file.exists():
        # ВАЖНО: поддерживаем оба формата component_passport.json
        # (legacy: {VNR:{...},SCO:{...}} и rich: {components:[...]})
        pp = None
        try:
            pp = model.load_component_passport(str(passport_file))
        except Exception:
            pp = None
        if not pp:
            pp = json.loads(passport_file.read_text(encoding="utf-8"))

        base_pp = dict(base_iso)
        base_pp["ISO_b_default"] = 0.30   # намеренно другое
        base_pp["ISO_m_default"] = 0.70
        base_pp["использовать_паспорт_компонентов"] = True
        base_pp["паспорт_компонентов_json"] = "component_passport.json"

        _nodes, _node_index, _edges, _B = model.build_network_full(base_pp)

        # VNR: сравним одну известную позицию
        code_vnr = "VNR-238-3/8"
        ent_vnr = (pp.get("VNR", {}) or {}).get(code_vnr, {}) or {}
        iso_vnr = ent_vnr.get("iso", {}) or {}
        C_ref = float(iso_vnr.get("C_m3_s_Pa", 0.0))
        b_ref = float(iso_vnr.get("b", 0.0))

        e_vnr = next((e for e in _edges if getattr(e, "camozzi_код", None) == code_vnr), None)
        if e_vnr is None or e_vnr.C_iso is None:
            print("  !! [7] не нашли ребро VNR-238-3/8 или у него нет C_iso")
            return _finalize(7)

        relC = abs(float(e_vnr.C_iso) - C_ref) / max(1e-12, abs(C_ref))
        relb = abs(float(e_vnr.b_iso or 0.0) - b_ref)
        print(f"[7] passport precedence VNR: relC={relC:.3e}, |b-b_ref|={relb:.3e}  (ISO_b_default={base_pp['ISO_b_default']})")

        if relC > 1e-9 or relb > 1e-9:
            print("  !! [7] ОШИБКА: похоже, паспорт не применяется (или структура JSON изменилась)")
            return _finalize(7)

        # SCO: проверим C_max (OPEN) на одной известной позиции
        code_sco = "SCO 606-1/4"
        ent_sco = (pp.get("SCO", {}) or {}).get(code_sco, {}) or {}
        iso_sco = ent_sco.get("iso", {}) or {}
        C_open_ref = float(iso_sco.get("C_open_m3_s_Pa", 0.0))
        b_sco_ref = float(iso_sco.get("b", 0.0))

        e_sco = next((e for e in _edges if getattr(e, "camozzi_код", None) == code_sco and getattr(e, "C_max", None) is not None), None)
        if e_sco is None or e_sco.C_max is None:
            print("  !! [7] не нашли ребро SCO 606-1/4 с C_max")
            return _finalize(7)

        relC2 = abs(float(e_sco.C_max) - C_open_ref) / max(1e-12, abs(C_open_ref))
        relb2 = abs(float(e_sco.b_iso or 0.0) - b_sco_ref)
        print(f"[7] passport precedence SCO: relC_open={relC2:.3e}, |b-b_ref|={relb2:.3e}")

        if relC2 > 1e-9 or relb2 > 1e-9:
            print("  !! [7] ОШИБКА: SCO паспорт не применяется (или структура JSON изменилась)")
            return _finalize(7)

        print("  OK: component_passport.json реально используется и имеет приоритет")
    else:
        print("[7] WARNING: component_passport.json not found, skipping precedence test")



    # --- 7b) iso6358_phi boundary behaviour (vacuum‑safe) ---
    # Цель: при p2->0 (вакуум/атм≈0) pr→0 => phi должно быть ~1.0 (choked‑режим), а не 0.
    # Иначе вблизи нулевого давления расчёт расхода «захлопывается».
    try:
        # Большинство наших моделей реализуют iso6358_phi(pr, b, m), где pr = p_down/p_up.
        # Для вакуума p_down=0 => pr=0 => ожидаем phi≈1 (choked flow).
        try:
            phi = float(model.iso6358_phi(0.0, b=0.5, m=0.6))
        except TypeError:
            # запасной вариант: без keyword-аргументов
            phi = float(model.iso6358_phi(0.0, 0.5, 0.6))

        print(f"[7b] iso6358_phi(pr=0) = {phi:.6g} (expected ~1.0)")
        if phi < 0.99:
            print("  !! [7b] WARNING: iso6358_phi should be ~1.0 for pr→0 (vacuum-safe). Проверьте реализацию.")
    except Exception as ex:
        print(f"[7b] WARNING: iso6358_phi boundary self-check skipped due to exception: {ex!r}")


    # --- 7c) Scheme integrity (fingerprint) + optional Camozzi-only enforcement ---
    # Цель: защититься от «тихих» изменений PNEUMO_SCHEME.json или подмены компонента.
    # Поведение:
    #   - если enforce_scheme_integrity=True: несовпадение -> ошибка self-check
    #   - иначе: предупреждение + печать диагностического сообщения
    try:
        from scheme_integrity import verify_scheme_integrity, enforce_camozzi_only as _enforce_camozzi_only

        scheme_path = HERE / "PNEUMO_SCHEME.json"
        fp_path = HERE / str(base.get("scheme_fingerprint_file", "scheme_fingerprint.json"))
        enforce = bool(base.get("enforce_scheme_integrity", False))

        if scheme_path.exists() and fp_path.exists():
            ok, msg = verify_scheme_integrity(str(scheme_path), str(fp_path))
            tag = "OK" if ok else ("FAIL" if enforce else "WARNING")
            print(f"[7c] scheme fingerprint: {tag}: {msg}")
            if (not ok) and enforce:
                print("  !! [7c] ОШИБКА: схема изменилась относительно эталона и enforce_scheme_integrity=True")
                return _finalize(7)
        else:
            print("[7c] WARNING: missing PNEUMO_SCHEME.json or fingerprint file, skipping scheme integrity check")

        enforce_cam = bool(base.get("enforce_camozzi_only", False))
        if enforce_cam:
            ok2, msg2 = _enforce_camozzi_only(str(scheme_path))
            print(f"[7c] camozzi-only: {'OK' if ok2 else 'FAIL'}: {msg2}")
            if not ok2:
                return _finalize(7)
    except Exception as ex:
        print(f"[7c] WARNING: scheme integrity self-check skipped due to exception: {ex!r}")

    # --- 8) gas energy balance (1st law closure) ---
    # Небольшой прогон, чтобы убедиться что добавленные поля считаются и баланс не «разваливается».
    try:
        suite_path = HERE / "default_suite.json"
        if suite_path.exists():
            suite_local = json.loads(suite_path.read_text(encoding="utf-8"))
            test_energy = next((t for t in suite_local if t.get("включен", True)), None)
        else:
            test_energy = None

        if test_energy is None:
            test_energy = {"имя": "energy_smoke", "тип": "инерция_крен", "dt": 0.01, "t_end": 0.2, "t_step": 0.05, "ay": 1.0}

        dtE = float(test_energy.get("dt", 0.01))
        tE = min(float(test_energy.get("t_end", 0.2)), 0.6)   # ограничим, чтобы self_check был быстрым

        outE = model.simulate(base, test_energy, dt=dtE, t_end=tE, record_full=False)
        df_atmE = outE[7]
        if "баланс_энергии_ошибка_Дж" in df_atmE.columns:
            err_abs = float(df_atmE["баланс_энергии_ошибка_Дж"].iloc[0])
            U_end = float(df_atmE.get("энергия_газа_конечная_Дж", [0.0])[0])
            tol = max(1.0, 1e-3 * abs(U_end))  # ~0.1% или 1 Дж

            print(f"[8] gas energy balance residual: {err_abs:.6g} J  (tol {tol:.3g} J)")
            if str(df_atmE.get("термодинамика", [""])[0]).strip().lower() != "isothermal":
                if abs(err_abs) > tol:
                    print("  !! [8] WARNING: energy balance error is larger than expected — проверьте dt/параметры или модель тепла/расхода")
                    _add('WARN','8','gas energy balance residual beyond tolerance', abs_dE_J=float(err_abs), tolerance_J=float(tol), thermo=str(df_atmE.get("термодинамика", [""])[0]))
        else:
            print("[8] WARNING: energy balance columns not found in df_atm (unexpected)")
            _add('WARN','8','missing df_atm energy balance columns')
    except Exception as ex:
        print(f"[8] WARNING: energy balance self-check skipped due to exception: {ex!r}")
        _add('WARN','8','gas energy balance self-check exception', exception=repr(ex))


    # --- 9) entropy/exergy balance (2nd law diagnostics) ---
    try:
        if df_atmE is not None and ("энтропия_генерация_Дж_К" in df_atmE.columns):
            Sgen = float(df_atmE["энтропия_генерация_Дж_К"].iloc[0])
            Xdest = float(df_atmE.get("эксергия_разрушена_Дж", [0.0])[0]) if hasattr(df_atmE, 'get') else 0.0
            thermo = str(df_atmE.get("термодинамика", [""])[0]).strip().lower()
            print(f"[9] entropy generation (cum): {Sgen:.6g} J/K, exergy destroyed: {Xdest:.6g} J")
            if thermo != 'isothermal':
                # допускаем небольшую отрицательность из-за численных ошибок
                if Sgen < -1e-6 * max(1.0, abs(Sgen)):
                    print("  !! [9] WARNING: S_gen < 0 (2nd law violation or numerical issue). Проверь dt/тепломодель/расход.")
                    _add('WARN','9','entropy generation negative (2nd law risk)', Sgen_J_per_K=float(Sgen))
        else:
            print("[9] WARNING: entropy/exergy columns not found in df_atm")
            _add('WARN','9','missing df_atm entropy/exergy columns')
    except Exception as ex:
        print(f"[9] WARNING: entropy/exergy self-check skipped due to exception: {ex!r}")
        _add('WARN','9','entropy/exergy self-check exception', exception=repr(ex))


    # --- 10) wall lumped-model validity (Biot number) ---
    try:
        if df_atmE is not None and ("стенка_Bi_max" in df_atmE.columns):
            Bi = float(df_atmE["стенка_Bi_max"].iloc[0])
            print(f"[10] wall Biot max: {Bi:.6g}  (lumped ok ~ Bi<0.1)")
            if "стенка_Bi_max_dyn" in df_atmE.columns:
                Bi_dyn = float(df_atmE["стенка_Bi_max_dyn"].iloc[0])
                print(f"[10] wall Biot max (dyn): {Bi_dyn:.6g}")
            if Bi > 0.1:
                print("  !! [10] WARNING: Biot > 0.1 -> стенка может быть НЕ изотермична по толщине; lumped‑модель даст заметную ошибку.")
                _add('WARN','10','Biot > 0.1 (lumped wall model questionable)', Biot_max=float(Bi), threshold=0.1)
        else:
            print("[10] WARNING: wall Biot column not found in df_atm")
            _add('WARN','10','missing df_atm wall Biot columns')
    except Exception as ex:
        print(f"[10] WARNING: wall Biot self-check skipped due to exception: {ex!r}")
        _add('WARN','10','wall Biot self-check exception', exception=repr(ex))

    print("\nSELF-CHECK: OK")
    return _finalize(0)


if __name__ == "__main__":
    raise SystemExit(main())
