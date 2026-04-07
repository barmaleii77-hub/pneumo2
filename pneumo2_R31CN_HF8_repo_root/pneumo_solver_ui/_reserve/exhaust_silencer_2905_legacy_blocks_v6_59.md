# RESERVED — Legacy exhaust silencer 2905 code blocks (v6_59)
Этот файл сохраняет прежний код моделирования глушителей выхлопа (2905) как резерв.
В релизе v6_60 схема приведена к источнику истины: после SCO → сразу АТМ.

## model_pneumo_v8_energy_audit_vacuum.py

### Pmax (SCO + SIL)

```python

    # Разделение выхлопа на две последовательные потери: дроссель SCO и глушитель 2905 (опционально).
    split_exhaust_silencer = bool(params.get('разделить_SCO_и_глушитель_2905', True))

    if split_exhaust_silencer:
        # Дроссель SCO (без учёта глушителя)
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'узел_после_дросселя_выхлоп_Pmax', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)

        # Глушитель (SIL)
        sil_code = str(params.get('код_глушителя_выхлоп_Pmax', '2905 1/4'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmax',
                 'узел_после_дросселя_выхлоп_Pmax', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        # Старый режим: SCO+2905 как один эквивалентный элемент (коэф_потока_глушителя_2905 масштабирует Qn/C).
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4+2905", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)
```

### Conditional block #1 (split_exhaust_silencer)

```python

    if split_exhaust_silencer:
        # Дроссель SCO (без учёта глушителя)
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'узел_после_дросселя_выхлоп_Pmax', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)

        # Глушитель (SIL)
        sil_code = str(params.get('код_глушителя_выхлоп_Pmax', '2905 1/4'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmax',
                 'узел_после_дросселя_выхлоп_Pmax', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        # Старый режим: SCO+2905 как один эквивалентный элемент (коэф_потока_глушителя_2905 масштабирует Qn/C).
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4+2905", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)
```

### Conditional block #2 (split_exhaust_silencer)

```python

    if split_exhaust_silencer:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8", alpha_дроссель_выхлоп_Pmid)
        add_edge('дроссель_выхлоп_Pmid',
                 'узел_после_ОК_Pmid', 'узел_после_дросселя_выхлоп_Pmid', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmid)

        sil_code = str(params.get('код_глушителя_выхлоп_Pmid', '2905 1/8'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmid',
                 'узел_после_дросселя_выхлоп_Pmid', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8+2905", alpha_дроссель_выхлоп_Pmid)
        add_edge('дроссель_выхлоп_Pmid',
                 'узел_после_ОК_Pmid', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmid)
```

### Conditional block #3 (split_exhaust_silencer)

```python

    if split_exhaust_silencer:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8", alpha_дроссель_выхлоп_Pmin)
        add_edge('дроссель_выхлоп_Pmin',
                 'узел_после_ОК_Pmin', 'узел_после_дросселя_выхлоп_Pmin', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmin)

        sil_code = str(params.get('код_глушителя_выхлоп_Pmin', '2905 1/8'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmin',
                 'узел_после_дросселя_выхлоп_Pmin', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8+2905", alpha_дроссель_выхлоп_Pmin)
        add_edge('дроссель_выхлоп_Pmin',
                 'узел_после_ОК_Pmin', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmin)
```

## model_pneumo_v9_mech_doublewishbone_r48_reference.py

### Pmax (SCO + SIL)

```python

    # Разделение выхлопа на две последовательные потери: дроссель SCO и глушитель 2905 (опционально).
    split_exhaust_silencer = bool(params.get('разделить_SCO_и_глушитель_2905', True))

    if split_exhaust_silencer:
        # Дроссель SCO (без учёта глушителя)
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'узел_после_дросселя_выхлоп_Pmax', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)

        # Глушитель (SIL)
        sil_code = str(params.get('код_глушителя_выхлоп_Pmax', '2905 1/4'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmax',
                 'узел_после_дросселя_выхлоп_Pmax', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        # Старый режим: SCO+2905 как один эквивалентный элемент (коэф_потока_глушителя_2905 масштабирует Qn/C).
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4+2905", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)
```

### Conditional block #1 (split_exhaust_silencer)

```python

    if split_exhaust_silencer:
        # Дроссель SCO (без учёта глушителя)
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'узел_после_дросселя_выхлоп_Pmax', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)

        # Глушитель (SIL)
        sil_code = str(params.get('код_глушителя_выхлоп_Pmax', '2905 1/4'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmax',
                 'узел_после_дросселя_выхлоп_Pmax', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        # Старый режим: SCO+2905 как один эквивалентный элемент (коэф_потока_глушителя_2905 масштабирует Qn/C).
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 606-1/4+2905", alpha_дроссель_выхлоп_Pmax)
        add_edge('дроссель_выхлоп_Pmax',
                 'узел_после_предохран_Pmax', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 606-1/4+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmax)
```

### Conditional block #2 (split_exhaust_silencer)

```python

    if split_exhaust_silencer:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8", alpha_дроссель_выхлоп_Pmid)
        add_edge('дроссель_выхлоп_Pmid',
                 'узел_после_ОК_Pmid', 'узел_после_дросселя_выхлоп_Pmid', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmid)

        sil_code = str(params.get('код_глушителя_выхлоп_Pmid', '2905 1/8'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmid',
                 'узел_после_дросселя_выхлоп_Pmid', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8+2905", alpha_дроссель_выхлоп_Pmid)
        add_edge('дроссель_выхлоп_Pmid',
                 'узел_после_ОК_Pmid', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmid)
```

### Conditional block #3 (split_exhaust_silencer)

```python

    if split_exhaust_silencer:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8", alpha_дроссель_выхлоп_Pmin)
        add_edge('дроссель_выхлоп_Pmin',
                 'узел_после_ОК_Pmin', 'узел_после_дросселя_выхлоп_Pmin', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmin)

        sil_code = str(params.get('код_глушителя_выхлоп_Pmin', '2905 1/8'))
        A_sil, _dp_sil, C_sil, b_sil, m_sil = A_по_SIL(sil_code)
        add_edge('глушитель_выхлоп_Pmin',
                 'узел_после_дросселя_выхлоп_Pmin', 'АТМ', 'orifice', A_sil, dp_crack=0.0,
                 group='выхлоп', camozzi_код=sil_code, C_iso=C_sil, b_iso=b_sil, m_iso=m_sil)
    else:
        A_eff, A_open, A_closed, _Ageom, C_eff, C_open, C_closed, _Qn_eff, _Qn_open, _Qn_closed, b_iso, m_iso = A_по_SCO("SCO 604-1/8+2905", alpha_дроссель_выхлоп_Pmin)
        add_edge('дроссель_выхлоп_Pmin',
                 'узел_после_ОК_Pmin', 'АТМ', 'orifice', A_eff, dp_crack=0.0,
                 group='выхлоп', camozzi_код="SCO 604-1/8+2905", C_iso=C_eff, b_iso=b_iso, m_iso=m_iso, C_min=C_closed, C_max=C_open, A_мин=A_closed, A_макс=A_open, alpha=alpha_дроссель_выхлоп_Pmin)
```
