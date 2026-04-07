# Matematika55 — Release Notes (поверх ObobshchenieR43)

Дата: **2026-01-25** (Europe/Amsterdam)

База: **ObobshchenieR43**  
Цель релиза: **убрать нефизичность и «энерго‑утечки» при включённом сглаживании контактов**, сделать сглаживание управляемым из UI и добавить автоматическую проверку корректности.

---

## 1) Главное изменение: energy‑consistent сглаженный контакт (шина + отбойники)

В `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py` исправлена консервативная часть сил в режиме `smooth_contacts=True`.

**Проблема:**  
Ранее использовалось:
- `F_tire_spring = k_tire * pen_pos`  
- `F_stop_spring = k_stop * over_pos` (и аналогично для under)

При этом механическая потенциальная энергия считалась как:
- `U_tire = 0.5*k_tire*sum(pen_pos**2)`  
- `U_stop = 0.5*k_stop*sum(over_pos**2 + under_pos**2)`

То есть **сила не была производной от U по проникновению**, потому что не учитывался множитель `d(pos)/dx`.

**Исправление (энерго‑согласованно):**
- `F_tire = (k_tire*pen_pos + c_tire*pen_dot_pos) * g_contact`, где `g_contact = d(pen_pos)/d(pen)`
- `F_stop = (k_stop*over_pos + c_stop*delta_dot_pos) * g_over - (k_stop*under_pos + c_stop*delta_dot_neg) * g_under`

Теперь выполняется:
- консервативная часть: `F_spring = d/dx (0.5*k*pos(x)^2) = k*pos(x)*dpos/dx`
- диссипативная часть остаётся односторонней и не создаёт энергию.

Это **уменьшает ошибку механического энерго‑баланса** в smooth‑режиме и делает модель корректнее для градиентной оптимизации.

---

## 2) Preflight Gate: добавлена проверка согласованности контакта с U(x)

Добавлен новый быстрый тест:
- `pneumo_solver_ui/tools/contact_models_property_check.py`

Он проверяет:
- что в коде действительно используется энерго‑согласованная формула (по паттернам)
- что численно `dU/dx ≈ F_spring` для `U=0.5*k*pos(x)^2` и текущих `smooth_pos/smooth_pos_grad`

Тест включён в:
- `pneumo_solver_ui/tools/preflight_gate.py`

---

## 3) Параметры сглаживания вынесены в default_base.json и UI

В `pneumo_solver_ui/default_base.json` добавлены ключи (с безопасными дефолтами):

- `smooth_dynamics`, `smooth_mechanics`, `smooth_stroke`, `smooth_contacts`, `smooth_spring`, `smooth_pressure_floor`
- `smooth_eps_pos_m`, `smooth_eps_vel_mps`, `smooth_eps_mass_kg`, `smooth_eps_vol_m3`
- `road_dot_eps`

В `pneumo_solver_ui/pneumo_ui_app.py` добавлены описания этих параметров в `PARAM_META`, чтобы они отображались в UI в группе **«Сглаживание»**.

---

## 4) Дифы/патчи

В релиз включены:

- `patches/Matematika55_from_ObobshchenieR43.patch`
- `patches/Matematika55_from_Matematika54.patch`
- `diffs/Matematika55_vs_ObobshchenieR43.diff`
- `diffs/Matematika55_vs_Matematika54.diff`

---

## 5) Что дальше (рекомендуемый следующий шаг)

1) Сделать аналогичную энерго‑согласованную схему для **пружины** при включённом `smooth_spring=True`, если клип пружины реально используется оптимизатором.
2) Добавить «эталонные» тесты на мех. энерго‑баланс для нескольких профилей дороги (ступенька/синус/бугор) и разных dt.
3) Завести явный режим `smooth_mode="energy_consistent"` vs `"legacy"`, чтобы можно было сравнивать поведение.

