"""ISV 2026 estimate — Imposto Sobre Veículos (Portuguese vehicle tax).

Tabela A (passenger cars / ligeiros de passageiros), WLTP. Cross-checked 2026-06 against
impostosobreveiculos.info / ecoimport.pt / autogo.pt (2026 = 2025 tables, no OE2026 increase).

ESTIMATE for the main cases (petrol/diesel/hybrid/PHEV/electric, WLTP). NOT a substitute
for the official AT simulator: ignores NEDC, light-commercial tables, regional specifics,
exact month-based age rounding, and IVA on the diesel surcharge.
"""
import calendar
import datetime
from decimal import Decimal, ROUND_HALF_UP

INF = 10 ** 9

# Componente cilindrada — (max_cc_inclusive, taxa €/cm³, parcela a abater €). All fuels.
CILINDRADA = [
    (1000, 1.09, 849.03),
    (1250, 1.18, 850.69),
    (INF, 5.61, 6194.88),
]

# Componente ambiental WLTP — (max_co2_g/km, taxa €/g, parcela a abater €)
CO2_PETROL = [   # gasolina / GPL / gás natural
    (110, 0.44, 43.02), (115, 1.10, 115.80), (120, 1.38, 147.79),
    (130, 5.27, 619.17), (145, 6.38, 762.73), (175, 41.54, 5819.56),
    (195, 51.38, 7247.39), (235, 193.01, 34190.52), (INF, 233.81, 41910.96),
]
CO2_DIESEL = [   # gasóleo
    (110, 1.72, 11.50), (120, 18.96, 1906.19), (140, 65.04, 7360.85),
    (150, 127.40, 16080.57), (160, 160.81, 21176.06), (170, 221.69, 29227.38),
    (190, 274.08, 36987.98), (INF, 282.35, 38271.32),
]
# NEDC environmental tables (cars first-registered before WLTP, ~pre-2020). Much steeper —
# a 120 g/km NEDC petrol = €2207 vs €17 WLTP. Using the wrong standard is the #1 ISV error.
CO2_PETROL_NEDC = [
    (99, 4.62, 427.00), (115, 8.09, 750.99), (145, 52.56, 5903.94),
    (175, 61.24, 7140.17), (195, 155.97, 23627.27), (INF, 205.65, 33390.12),
]
CO2_DIESEL_NEDC = [
    (79, 5.78, 439.04), (95, 23.45, 1848.58), (120, 79.22, 7195.63),
    (140, 175.73, 18924.92), (160, 195.43, 21720.92), (INF, 268.42, 33447.90),
]
DIESEL_PARTICULATE = 500.0   # ligeiros passageiros, partículas ≥ 0,001 g/km
MIN_ISV = 100.0   # Art. 7.º n.º 4: "o total do imposto a pagar não pode ser inferior a € 100"
#                   (applies to Tabela A and Tabela B / autocaravanas; NOT motociclos — art. 10)


def nedc_for_year(year) -> bool:
    """Heuristic: cars first-registered before 2020 are homologated NEDC; 2020+ are WLTP."""
    return bool(year and int(year) < 2020)

# Tabela D — redução por anos de uso (used EU imports), applied to the whole ISV (Art. 11º).
# Bracket lookup uses `years < hi` (strict upper). VERIFIED 2026-06 against the live AT
# simulator: a car first-registered EXACTLY N years ago lands in the ">N to N+1" bracket —
# e.g. registered 30/06/2023, valued 30/06/2026 → 35% (not 28%); registered 30/06/2024 →
# 28% (not 20%). The simulator measures age as marginally > N years, so the next bracket up
# applies at the anniversary. (An earlier `<=` change here was WRONG — it under-charged.)
AGE_REDUCTION = [   # (age_years_strict_upper, pct)
    (1, 0.10), (2, 0.20), (3, 0.28), (4, 0.35), (5, 0.43),
    (6, 0.52), (7, 0.60), (8, 0.65), (9, 0.70), (10, 0.75), (INF, 0.80),
]

# PHEV 75%-reduction CO2 cap is now year-aware (see compute()): 80 g/km for Euro 6e-bis
# homologation (≈ registrations from 2026), else 50 g/km for Euro 6. Not a flat constant.


def _bracket(table, x):
    for hi, rate, ded in table:
        if x <= hi:
            return rate, ded
    return table[-1][1], table[-1][2]


def phev_co2_cap(year) -> int:
    """CISV art. 8.º n.º 1 d): PHEV CO2 gate (strict <) — 80 g/km for Euro 6e-bis homologation
    (approximated as first registration ≥ 2026; no homologation field), else 50 g/km."""
    return 80 if (year and int(year) >= 2026) else 50


def age_years_at(year, month=1, day=None, at=None) -> float:
    """Age (years) of a car first registered on year/month/day, measured CALENDAR-wise at
    `at` (default today): whole anniversaries passed + fraction of the current year. On the exact
    anniversary the result is exactly N.0, which `age_reduction`'s strict `<` puts in the next
    bracket up — the AT-verified behaviour (see AGE_REDUCTION). Unknown day → the LAST day of
    the month: never assumes an anniversary has passed when it may not have, so the reduction is
    never overstated (a day-1 assumption over-applied it for up to a month)."""
    if not year:
        return 0.0
    at = at or datetime.date.today()
    if isinstance(at, datetime.datetime):
        at = at.date()
    month = min(max(int(month or 1), 1), 12)
    last = calendar.monthrange(int(year), month)[1]
    reg = datetime.date(int(year), month, min(int(day), last) if day else last)
    if at <= reg:
        return 0.0

    def _ann(n):   # n-th anniversary; 29 Feb → 28 Feb in non-leap years
        y = reg.year + n
        return datetime.date(y, reg.month, min(reg.day, calendar.monthrange(y, reg.month)[1]))
    n = at.year - reg.year
    if _ann(n) > at:
        n -= 1
    a, b = _ann(n), _ann(n + 1)
    return n + (at - a).days / (b - a).days


def age_reduction(years: float) -> float:
    for hi, pct in AGE_REDUCTION:
        if years < hi:
            return pct
    return 0.80


def _r2(*factors) -> float:
    """Product of the factors, in exact decimal, rounded to cents half-up (the AT breakdown).
    Float maths + round() was binary/banker's — 666.06 × 0.75 = 499.5449999… came out 499.54
    instead of 499.55 (1 cent off the official figure)."""
    d = Decimal(1)
    for f in factors:
        d *= Decimal(repr(float(f)))
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _isv_lines(comp_cc: float, comp_amb: float, rate: float, surcharge: float,
               red: float) -> float:
    """Replicate the official AT 'Demonstração' line-by-line (each line rounded to cents,
    then combined) so the total matches the simulator to the cent:
        06 = 03 − 04a − 04b + 05 − 05a
    03 = (comp_cc + comp_amb) × rate ; 04a = comp_cc × rate × D ; 04b = comp_amb × rate × D ;
    05 = agravamento partículas ; 05a = 05 × D. comp_amb may be negative (netted)."""
    comp_cc = _r2(comp_cc)
    comp_amb = _r2(comp_amb)
    l03 = _r2(comp_cc + comp_amb, rate)
    # a "redução" line can't be negative — when the ambiental component is negative it still
    # NETS into l03, but its age-reduction line (04b) floors at 0 (matches the official AT
    # breakdown / importrust: a discount is never an add-back; re-confirmed 2026-10-30 on
    # importrust for used low-CO2 petrols: 823.23 − 1.22 − 353.99 = 468.02).
    l04a = max(0.0, _r2(comp_cc, rate, red))
    l04b = max(0.0, _r2(comp_amb, rate, red))
    l05 = _r2(surcharge)
    l05a = _r2(surcharge, red)
    total = max(0.0, _r2(l03 - l04a - l04b + l05 - l05a))
    # itemised like the official AT "Demonstração" (01..06) so the UI can mirror it exactly
    return {"comp_cc": comp_cc, "comp_amb": comp_amb, "rate_pct": round(rate * 100),
            "taxa_tabela": l03, "red_cc": l04a, "red_amb": l04b,
            "agravamento": l05, "red_agrav": l05a, "reducao_pct": round(red * 100),
            "total": total}


def compute(cc: int, co2: int, fuel: str, age_years: float, from_eu: bool = True,
            phev_range_km: int = 0, nedc: bool = False, used: bool = True,
            particulas: bool = True, pre1970: bool = False, year=None) -> dict:
    """Estimate ISV (€) — Tabela A (ligeiros de passageiros). fuel ∈ petrol/diesel/hybrid/
    phev/electric/lpg. Exact official AT formula (verified 2026-06 on the live simulator):
        ISV = max(0, [(comp_cilindrada + comp_ambiental) × rate% + agravamento] × (1 − D))
    The ambiental component is NETTED (a negative low-CO2 ambiental reduces cilindrada — the
    official does NOT floor it at 0). rate% applies to the components only; the diesel particle
    surcharge is added outside it and is itself reduced by the age reduction D.
    age_years from first registration; non-EU imports get no age reduction. used=False (novo)
    → no reduction. PHEV gets the 25% rate with range ≥ 50 km AND CO2 ≤ cap (cap = 80 g/km for
    Euro 6e-bis ≈ year ≥ 2026, else 50 g/km); non-plug-in hybrids get NO reduction (since 2021).
    nedc=True → NEDC tables (pre-2020)."""
    fuel = (fuel or "petrol").lower()
    cc = max(int(cc or 0), 0)
    co2 = max(int(co2 or 0), 0)
    # A mild/full hybrid is NOT a plug-in: it gets NO reduction and is taxed by its combustion
    # fuel. A diesel hybrid (48V MHEV "TDI", HEV) uses the gasóleo CO2 table + the particle
    # surcharge — exactly like a diesel. Only phev gets the intermediate rate (below).
    is_diesel = fuel in ("diesel", "hybrid_diesel")

    if fuel == "electric":
        return {"isv": 0.0, "exempt": True, "note": "100% elétrico — isento de ISV",
                "comp_cilindrada": 0.0, "comp_ambiental": 0.0, "diesel_surcharge": 0.0,
                "base": 0.0, "age_years": round(age_years, 1), "age_reduction_pct": 0}

    rc, dc = _bracket(CILINDRADA, cc)
    comp_cc = cc * rc - dc
    if is_diesel:
        co2_table = CO2_DIESEL_NEDC if nedc else CO2_DIESEL
    else:
        co2_table = CO2_PETROL_NEDC if nedc else CO2_PETROL
    rco2, dco2 = _bracket(co2_table, co2)
    comp_co2 = co2 * rco2 - dco2   # NOT floored — official nets a negative ambiental
    if pre1970:
        comp_co2 = 0.0   # matrícula pré-1970 → só cilindrada, sem componente ambiental
    diesel_sur = DIESEL_PARTICULATE if (is_diesel and particulas) else 0.0

    incentive, note = 1.0, None
    if fuel == "phev":
        r = phev_range_km or 0
        # CISV art. 8.º n.º 1 d) (Lei 73-A/2025): 25% with ≥50 km electric range AND CO2
        # STRICTLY below 50 g/km ("inferiores a"), or below 80 g/km for Euro 6e-bis homologation.
        # No homologation field on the form → approximate Euro 6e-bis by registration year ≥2026.
        co2_cap = phev_co2_cap(year)
        # art. 8.º n.º 1 e) (Lei 45-A/2024): 25% for PHEVs first registered in ANOTHER EU state
        # between 2015-01-01 and 2020-12-31 with ≥25 km electric range — no CO2 condition.
        legacy_eu = bool(from_eu and used and year and 2015 <= int(year) <= 2020 and r >= 25)
        if r >= 50 and co2 < co2_cap:
            incentive = 0.25
            note = "PHEV −75% (taxa intermédia, art. 8.º 1 d) — sujeito a confirmação da homologação e autonomia"
        elif legacy_eu:
            incentive = 0.25
            note = ("PHEV matriculado na UE em 2015–2020 com ≥25 km — taxa de 25% (art. 8.º 1 e); "
                    "confirme a autonomia elétrica no COC")
        else:
            incentive = 1.0
            note = (f"PHEV sem redução (requer ≥50 km e CO2 < {co2_cap} g/km, ou matrícula UE "
                    "2015–2020 com ≥25 km) — ISV integral.")
    # Híbridos não plug-in (HEV/mild/full): SEM redução desde 2021 → ISV integral.
    if pre1970:
        _p = "Matrícula pré-1970 — sem componente ambiental"
        note = f"{note} · {_p}" if note else _p

    red = age_reduction(age_years) if (from_eu and used) else 0.0
    bd = _isv_lines(comp_cc, comp_co2, incentive, diesel_sur, red)
    final = max(MIN_ISV, bd["total"])

    out = {"isv": round(final, 2), "exempt": False, "note": note, "table": "A",
           "comp_cilindrada": round(comp_cc, 2), "comp_ambiental": round(comp_co2, 2),
           "diesel_surcharge": diesel_sur, "base": round(comp_cc + comp_co2, 2),
           "rate_pct": round(incentive * 100), "min_isv_applied": final > bd["total"],
           "breakdown": bd, "age_years": round(age_years, 1),
           "age_reduction_pct": round(red * 100)}
    if fuel == "phev" and incentive < 1.0:
        # The AT simulator has no PHEV option → run it as gasolina/gasóleo there and this is
        # the number you get (line 06). PHEV ISV = this base × 25%. Exposed so the result is
        # self-verifiable against AT: same car as petrol/diesel → × 0.25.
        out["phev_base"] = round(_isv_lines(comp_cc, comp_co2, 1.0, diesel_sur, red)["total"], 2)
    return out


# ───────────────────────── Tabela B — ligeiros de mercadorias e mistos ──────────────────
# CIEC Art. 7º nº2: Tabela B uses ONLY a cilindrada component (NO CO2/ambiental). The amount
# is then taken at a percentage set by the body/seats/4x4 config (Art. 7º=100%, 8º=intermédia,
# 9º=reduzida). Verified 2024/2025/2026 (OE2026 unchanged).
TABELA_B = [   # (max_cc_inclusive, taxa €/cm³, parcela a abater €)
    (1250, 5.30, 3331.68),
    (INF, 12.58, 12138.47),
]
# CISV art. 7.º n.º 3: €500 on ALL diesel ligeiros, "reduzido para 250€ relativamente aos
# veículos ligeiros de mercadorias referidos no n.º 2 do artigo 9.º" — i.e. ONLY van_10.
# (Was applied to every Tabela B category → commercial_15/50/100 under-taxed by up to €250.)
DIESEL_PARTICULATE_B = 250.0
DIESEL_PARTICULATE_B_CATS = {"van_10"}

# Commercial category → % of the Tabela B amount actually paid.
COMMERCIAL_RATE = {
    "commercial_100": 1.00,   # caixa fechada, ≤3 lugares, altura caixa <120 cm (Art. 7º nº2)
    "van_10":         0.10,   # caixa aberta/fechada/sem caixa, ≤3 lugares — classic furgão (Art. 9º nº2)
    "commercial_15":  0.15,   # >3 lugares SEM 4x4; mistos PB>2300 c/ caixa ≥145cm (Art. 9º nº1)
    "commercial_50":  0.50,   # caixa aberta/sem caixa, >3 lugares, COM 4x4 (Art. 8º nº3 intermédia)
}


# ───────────────────────── Tabela C — motociclos / triciclos / quadriciclos ─────────────
# CIEC Art. 10º: a FIXED euro amount per cilindrada bracket (no per-cm³ rate, no CO2). The
# table has no bracket below 120 cm³ → those pay nothing. Electric → exempt (Art. 5º nº2).
TABELA_C = [   # (max_cc_inclusive, fixed ISV €)
    (250, 73.78), (350, 91.63), (500, 122.57), (750, 184.45), (INF, 245.14),
]
MOTO_MIN_CC = 120   # below this displacement there is no Tabela C bracket → ISV 0


# ───────────────────────── Autocaravanas (Art. 9º nº3 transitional ramp) ────────────────
# CONFIRMED against CIEC Art. 9º nº3 (informador.pt, 2026-06): an autocaravana pays a % of the
# Tabela B amount (cilindrada only, NO CO2), ramping by ASSESSMENT year: 40% (2024) → 60% (2025)
# → 80% (2026) → 100% (2027+). The % tracks the year the ISV is settled (import year), not the
# car's first registration; the age reduction (Tabela D) is then applied on top.
AUTOCARAVANA_PCT = {2024: 0.40, 2025: 0.60, 2026: 0.80, 2027: 1.00}


def autocaravana_pct(assess_year=None) -> float:
    y = int(assess_year or datetime.date.today().year)
    if y <= 2024:
        return 0.40
    return AUTOCARAVANA_PCT.get(y, 1.00)   # 2025→.60, 2026→.80, ≥2027→1.00


def compute_b(cc, fuel, age_years, category="van_10", from_eu=True, used=True,
              particulas=True):
    """ISV for a light commercial / mixed vehicle (Tabela B). category picks the % of the
    Tabela B amount (COMMERCIAL_RATE). Electric → exempt. Diesel particle surcharge (€250 for
    van_10 / art. 9.º n.º 2, €500 for the other categories — art. 7.º n.º 3) is age-reduced like
    the rest (art. 11.º n.º 1). particulas=False (COC shows <0.001 g/km) drops it."""
    fuel = (fuel or "diesel").lower()
    cc = max(int(cc or 0), 0)
    rate = COMMERCIAL_RATE.get(category, 1.00)
    if fuel == "electric":
        return {"isv": 0.0, "exempt": True, "note": "Comercial 100% elétrico — isento",
                "table": "B", "base": 0.0, "rate_pct": round(rate * 100),
                "diesel_surcharge": 0.0, "age_reduction_pct": 0}
    taxa, parcela = _bracket(TABELA_B, cc)
    comp_cc = cc * taxa - parcela   # Tabela B has no ambiental component
    _sur = DIESEL_PARTICULATE_B if category in DIESEL_PARTICULATE_B_CATS else DIESEL_PARTICULATE
    surcharge = _sur if (fuel in ("diesel", "hybrid_diesel") and particulas) else 0.0
    red = age_reduction(age_years) if (from_eu and used) else 0.0
    bd = _isv_lines(comp_cc, 0.0, rate, surcharge, red)   # Tabela B, no ambiental
    final = max(MIN_ISV, bd["total"])
    return {"isv": round(final, 2), "exempt": False, "note": None, "table": "B",
            "base": round(comp_cc, 2), "rate_pct": round(rate * 100),
            "diesel_surcharge": surcharge, "min_isv_applied": final > bd["total"],
            "breakdown": bd, "age_years": round(age_years, 1),
            "age_reduction_pct": round(red * 100)}


def compute_moto(cc, age_years, fuel="petrol", from_eu=True, used=True):
    """ISV for a motorcycle/trike/quad (Tabela C). Fixed amount by cc; <120cc or electric → 0.
    Age reduction (Tabela D) applies to the fixed amount for used EU imports."""
    cc = max(int(cc or 0), 0)
    if (fuel or "petrol").lower() == "electric" or cc < MOTO_MIN_CC:
        return {"isv": 0.0, "exempt": True, "table": "C", "base": 0.0,
                "note": "Isento (elétrico ou < 120 cm³)", "age_reduction_pct": 0}
    base = next(v for hi, v in TABELA_C if cc <= hi)
    red = age_reduction(age_years) if (from_eu and used) else 0.0
    bd = _isv_lines(base, 0.0, 1.0, 0.0, red)   # Tabela C: fixed amount, no min-100 (art. 10)
    return {"isv": round(bd["total"], 2), "exempt": False, "table": "C", "base": round(base, 2),
            "note": None, "breakdown": bd, "age_years": round(age_years, 1),
            "age_reduction_pct": round(red * 100)}


def compute_autocaravana(cc, fuel, age_years, from_eu=True, used=True, particulas=True,
                         assess_year=None):
    """ISV for a motorhome (autocaravana). Art. 9º nº3: a % of the Tabela B amount (cilindrada
    only, no CO2) — 80% in 2026 — then the age reduction. Electric → exempt. Diesel particle
    surcharge: autocaravanas are ligeiros, so the 500€ agravamento applies to diesel."""
    fuel = (fuel or "diesel").lower()
    cc = max(int(cc or 0), 0)
    pct = autocaravana_pct(assess_year)
    if fuel == "electric":
        return {"isv": 0.0, "exempt": True, "table": "B/autocaravana", "base": 0.0,
                "autocaravana_pct": round(pct * 100), "note": "100% elétrico — isento",
                "age_reduction_pct": 0}
    taxa, parcela = _bracket(TABELA_B, cc)
    comp_cc = cc * taxa - parcela
    surcharge = DIESEL_PARTICULATE if (fuel in ("diesel", "hybrid_diesel") and particulas) else 0.0
    red = age_reduction(age_years) if (from_eu and used) else 0.0
    bd = _isv_lines(comp_cc, 0.0, pct, surcharge, red)
    final = max(MIN_ISV, bd["total"])
    return {"isv": round(final, 2), "exempt": False, "table": "B/autocaravana",
            "base": round(comp_cc, 2), "autocaravana_pct": round(pct * 100),
            "diesel_surcharge": surcharge, "min_isv_applied": final > bd["total"],
            "breakdown": bd, "age_years": round(age_years, 1),
            "age_reduction_pct": round(red * 100),
            "note": f"Autocaravana — {round(pct*100)}% da Tabela B (Art. 9º nº3)"}


# Heavy vehicles (>3500 kg) are OUTSIDE the ISV incidence entirely (CISV Art. 2º nº1 lists
# only ligeiros ≤3500 kg, autocaravanas and motos). Pesados de mercadorias and pesados de
# passageiros/autocarros are *não sujeitos* — a distinct state from "isento" (an exemption of
# an otherwise-due tax). We return it explicitly rather than €0 through a passenger path.
PESADOS = {"pesados_mercadorias", "pesados_passageiros", "autocarro"}


def compute_isv(category, cc=0, co2=0, fuel="petrol", age_years=0.0, year=None,
                from_eu=True, phev_range_km=0, used=True, particulas=True):
    """Unified entry. category:
    passenger | autocaravana | motorcycle | commercial_100 | van_10 | commercial_15 |
    commercial_50 | pesados_mercadorias | pesados_passageiros
    """
    cat = (category or "passenger").lower()
    nedc = nedc_for_year(year)
    pre1970 = bool(year and year < 1970)
    if cat in PESADOS:
        # Não sujeição (Art. 2º) — heavy vehicles never enter Tabela A/B/C.
        return {"isv": 0.0, "exempt": True, "not_subject": True, "table": None,
                "note": "Veículo pesado (>3500 kg) — não sujeito a ISV (Art. 2º CISV)",
                "age_reduction_pct": 0}
    if cat == "motorcycle":
        res = compute_moto(cc, age_years, fuel, from_eu, used)
    elif cat == "autocaravana":
        res = compute_autocaravana(cc, fuel, age_years, from_eu, used, particulas)
    elif cat in COMMERCIAL_RATE:
        res = compute_b(cc, fuel, age_years, cat, from_eu, used, particulas)
    else:
        res = compute(cc, co2, fuel, age_years, from_eu, phev_range_km, nedc, used,
                      particulas, pre1970, year)
    # Classic-vehicle advisory (≥30 anos): NO ISV exemption by age exists — but the car may
    # qualify for IUC exemption with a Veículo de Interesse Histórico (VIH) certificate.
    # Not automatic (individual AT decision, occasional use, <500 km/ano). Informational only.
    if age_years >= 30 and not res.get("exempt"):
        adv = ("Clássico (30+ anos): sem isenção de ISV pela idade; possível isenção de IUC "
               "com certificado de Veículo de Interesse Histórico (uso ocasional).")
        res["note"] = f"{res['note']} · {adv}" if res.get("note") else adv
        res["classic"] = True
    return res
