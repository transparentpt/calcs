"""IUC 2026 estimate — Imposto Único de Circulação (annual road tax), Categoria B.

For passenger cars first-registered after 1 July 2007 (Categoria B). Tables cross-checked
2026-06 (impostosobreveiculos.info, maisvalias) — 2026 = 2025 values, no OE2026 change.
Formula: IUC = (taxa_cilindrada + taxa_CO2) × coeficiente_ano + adicional_gasóleo(diesel)
+ adicional_CO2(matrícula ≥2017). 100% electric = exempt. PHEV/hybrid pay normal IUC.

ESTIMATE — Categoria B (≥2007) by cc+CO2; Categoria A (<2007) by cc × year-band (no CO2).
Not the official AT figure.
"""
from decimal import Decimal, ROUND_HALF_UP

INF = 10 ** 9


def _r2(x: float) -> float:
    """Cents, half-up in exact decimal (float round(202.125) gave 202.12)."""
    return float(Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

CILINDRADA = [(1250, 31.77), (1750, 63.74), (2500, 127.35), (INF, 435.84)]
CO2 = [(140, 65.15), (205, 97.63), (260, 212.04), (INF, 363.25)]          # WLTP
CO2_ADIC = [(140, 0.0), (205, 0.0), (260, 31.77), (INF, 63.74)]          # WLTP, matrícula ≥ 2017
CO2_NEDC = [(120, 65.15), (180, 97.63), (250, 212.04), (INF, 363.25)]     # pre-2020 cars
CO2_ADIC_NEDC = [(120, 0.0), (180, 0.0), (250, 31.77), (INF, 63.74)]      # NEDC, matrícula ≥ 2017
DIESEL_ADIC = [(1250, 5.02), (1750, 10.07), (2500, 20.12), (INF, 68.85)]

# Categoria A — ligeiros passageiros matriculados até 30/06/2007. By cilindrada × year-band:
# band 0 = posterior a 1995 (1996+), 1 = 1990-1995, 2 = 1981-1989 (and older, approx).
# AT splits the base by fuel into THREE bracket scales (same € values, different cc cutoffs) —
# verified vs AT "Consulta IUC 2026" (temp/IUC*.pdf). Diesel/GPL cap at 158,31 (no 287/512 tiers).
CAT_A_GAS = [                    # Combustível Gasolina — 6 brackets
    (1000, (19.90, 12.55, 8.80)),
    (1300, (39.95, 22.45, 12.55)),
    (1750, (62.40, 34.87, 17.49)),
    (2600, (158.31, 83.49, 36.09)),
    (3500, (287.49, 156.54, 79.72)),
    (INF,  (512.23, 263.11, 120.90)),
]
CAT_A_OUTROS = [                 # Combustível Outros produtos (gasóleo/GPL) — 4 brackets
    (1500, (19.90, 12.55, 8.80)),
    (2000, (39.95, 22.45, 12.55)),
    (3000, (62.40, 34.87, 17.49)),
    (INF,  (158.31, 83.49, 36.09)),
]
CAT_A_DIESEL_ADD = [
    (1500, (3.14, 1.98, 1.39)),
    (2000, (6.31, 3.55, 1.98)),
    (3000, (9.86, 5.51, 2.76)),
    (INF,  (25.01, 13.19, 5.70)),
]

# Categoria E — motociclos, ciclomotores, triciclos e quadriciclos. Flat annual amount by
# cilindrada × ano-de-matrícula band. NO CO2, NO age reduction (unlike ISV). 2026 = 2025.
# Isento: < 120 cm³, elétrico, matrícula < 1992, e 120–250 cm³ matriculado 1992–1996.
# Band 0 = matrícula 1997+ · band 1 = 1992–1996.
# PROVISIONAL — statutory table (CIUC art. 10, cross-checked impostosobreveiculos +
# motojornal 2026). Confirm the 8 AT-simulador cases in HANDOFF-taxes-moto.md before deploy.
CAT_E = [                       # (max_cc_inclusive, (taxa_1997+, taxa_1992_1996))
    (119, (0.0,    0.0)),
    (250, (6.19,   0.0)),
    (350, (8.76,   6.19)),
    (500, (21.18,  12.53)),
    (750, (63.62,  37.47)),
    (INF, (138.15, 67.76)),
]


def _cat_e_band(year: int | None) -> int:
    return 1 if (year and 1992 <= year <= 1996) else 0


def _amt(table, x):
    for hi, v in table:
        if x <= hi:
            return v
    return table[-1][1]


def _cat_a_band(year: int) -> int:
    if year >= 1996:
        return 0
    if year >= 1990:
        return 1
    return 2


def _amt3(table, x, band):
    for hi, vs in table:
        if x <= hi:
            return vs[band]
    return table[-1][1][band]


def coef(year) -> float:
    if not year or year <= 2007:
        return 1.00
    return {2008: 1.05, 2009: 1.10}.get(year, 1.15)


MIN_LIQUIDACAO = 10.0   # CIUC art. 16.º n.º 6 (n.º 11 from 2027): below €10 nothing is assessed


def _below_min(iuc: float, category: str, extra: dict) -> dict | None:
    """Art. 16.º: an annual IUC under €10 is not assessed (it is NOT a €10 floor)."""
    if 0 < iuc < MIN_LIQUIDACAO:
        return {"iuc": 0.0, "exempt": True, "category": category, "below_min": True,
                "note": f"IUC calculado ({iuc:.2f} €) inferior a 10 € — não há liquidação (art. 16.º CIUC).",
                **extra}
    return None


def compute_moto_e(cc: int, fuel: str, year: int | None) -> dict:
    """Annual IUC (€) for a motorcycle — Categoria E. Flat by cilindrada × ano-band, no CO2,
    no age reduction. Electric, < 120 cm³, matrícula < 1992, or 120–250 cm³ de 1992–1996 → isento."""
    fuel = (fuel or "petrol").lower()
    cc = max(int(cc or 0), 0)
    if fuel == "electric":
        return {"iuc": 0.0, "exempt": True, "category": "E", "note": "100% elétrico — isento de IUC"}
    if cc < 120:
        return {"iuc": 0.0, "exempt": True, "category": "E",
                "note": "Motociclo até 119 cm³ — isento de IUC"}
    if year and year < 1992:
        return {"iuc": 0.0, "exempt": True, "category": "E",
                "note": "Matrícula anterior a 1992 — isento de IUC (Categoria E)"}
    base = _amt3(CAT_E, cc, _cat_e_band(year))
    if base <= 0:               # 120–250 cm³ matriculado 1992–1996
        return {"iuc": 0.0, "exempt": True, "category": "E", "note": "Isento de IUC (Categoria E)"}
    return _below_min(round(base, 2), "E", {"taxa_cilindrada": round(base, 2)}) or {
            "iuc": round(base, 2), "exempt": False, "category": "E", "note": None,
            "taxa_cilindrada": round(base, 2), "taxa_co2": 0.0, "coef": 1.0,
            "diesel_adic": 0.0, "co2_adic": 0.0}


def compute(cc: int, co2: int, fuel: str, year: int | None,
            vehicle_type: str = "passenger", month: int | None = None) -> dict:
    """Annual IUC (€). vehicle_type=motorcycle → Categoria E; else Categoria A (first registered
    1981-01-01 … 2007-06-30) / Categoria B (from 2007-07-01, Lei 22-A/2007 art. 14.º n.º 2;
    CIUC art. 2.º n.º 1 a/b) — 2007 needs the month; unknown month → B. Before 1981 → outside
    Cat A, não sujeito. electric=isento."""
    if (vehicle_type or "").lower() == "motorcycle":
        return compute_moto_e(cc, fuel, year)
    fuel = (fuel or "petrol").lower()
    if fuel == "electric":
        return {"iuc": 0.0, "exempt": True, "note": "100% elétrico — isento de IUC", "category": "B"}
    # Diesel hybrid (MHEV/HEV TDI) carries the diesel IUC surcharge; petrol hybrid does not.
    is_diesel = fuel in ("diesel", "hybrid_diesel")
    if year and year < 1981:
        return {"iuc": 0.0, "exempt": True, "not_subject": True, "category": None,
                "note": "Matrícula anterior a 1981 — fora da Categoria A, não sujeito a IUC (art. 2.º CIUC)."}
    if year and (year < 2007 or (year == 2007 and month and int(month) < 7)):
        # Categoria A — cilindrada × ano de matrícula (sem CO2). Base bracket scale depends on
        # fuel (gasolina vs outros produtos); gasóleo also carries the adicional.
        cc = max(int(cc or 0), 0)
        band = _cat_a_band(int(year))
        is_gas = fuel in ("petrol", "gasoline", "gasolina", "hybrid", "phev")   # petrol (plug-in) hybrid → gasolina scale
        base = _amt3(CAT_A_GAS if is_gas else CAT_A_OUTROS, cc, band)
        dadd = _amt3(CAT_A_DIESEL_ADD, cc, band) if is_diesel else 0.0
        _m = _below_min(round(base + dadd, 2), "A", {"taxa_cilindrada": base, "diesel_adic": dadd})
        if _m:
            return _m
        return {"iuc": round(base + dadd, 2), "exempt": False, "category": "A",
                "note": "Categoria A (pré-2007). 30+ anos com certificado histórico → possível isenção.",
                "taxa_cilindrada": base, "taxa_co2": 0.0, "coef": 1.0,
                "diesel_adic": dadd, "co2_adic": 0.0}
    cc = max(int(cc or 0), 0)
    co2 = max(int(co2 or 0), 0)
    nedc = bool(year and year < 2020)   # pre-2020 cars use the NEDC CO2 brackets
    cil = _amt(CILINDRADA, cc)
    c2 = _amt(CO2_NEDC if nedc else CO2, co2)
    k = coef(year)
    co2_adic = _amt(CO2_ADIC_NEDC if nedc else CO2_ADIC, co2) if (year and year >= 2017) else 0.0
    # CIUC art. 10.º n.º 3: the year coefficient multiplies "a coleta obtida a partir das tabelas
    # previstas nos números anteriores" — n.º 1 (cc + CO2) AND the n.º 2 CO2 adicional. The diesel
    # adicional comes from a separate law (Lei 82-B/2014 art. 216.º) and stays outside it.
    base = (cil + c2 + co2_adic) * k
    diesel_adic = _amt(DIESEL_ADIC, cc) if is_diesel else 0.0
    iuc = _r2(base + diesel_adic)
    return {"iuc": iuc, "exempt": False, "note": None, "category": "B",
            "taxa_cilindrada": cil, "taxa_co2": c2, "coef": k,
            "diesel_adic": diesel_adic, "co2_adic": co2_adic}


# ══════════════════════ Categorias C / D — automóveis de mercadorias (por PESO BRUTO) ═════
# CIUC art. 11º (C = transporte particular) / art. 12º (D = público/aluguer). Base tributável
# (art. 7º c): peso bruto, nº de eixos, tipo de suspensão dos eixos motores, antiguidade da 1ª
# matrícula — SEM cilindrada, SEM CO2. Every `automóvel de mercadorias` (ligeiro OR pesado) is
# taxed here, never Categoria B (art. 2º só põe passageiros/mistos≤2500 na base cc+CO2).
# Default = C (particular) pela presunção do art. 2º nº3; D só com afetação a transporte público.
#
# Values: 2026 = 2025 = 2024 (Lei 82/2023 + Declaração de Retificação 10/2024; OE2026/Lei
# 73-A/2025 não alterou o IUC). <12t tem escalão único por peso; ≥12t é matriz peso×eixos×
# suspensão×ano (5 bandas) + sub-tabela de articulados/conjuntos. The ≥12t matrix lives in the
# baked JSON (iuc_pesados_2026.json) — 500+ cells, loaded once, not transcribed here by hand.
import json as _json
import os as _os

MINIMO_COBRANCA = 10.0        # art. 16º nº6 — abaixo de 10 € não há liquidação
REGIAO_AUTONOMA_DESCONTO = 0.5  # art. 5º nº8 b) — Açores/Madeira, uso exclusivo na região

# <12 t — escalão único por peso bruto (sem eixos/suspensão). (max_kg_inclusive, €).
CAT_C_LEVES = [(2500, 35.15), (3500, 58.21), (7500, 139.47), (11999, 226.24)]
CAT_D_LEVES = [(2500, 9.25),  (3500, 15.77), (7500, 35.88),  (11999, 59.80)]

# ≥12 t registration-year bands — key = lower bound of the band. 1990=≤1990, 1991=1991-1993,
# 1994=1994-1996, 1997=1997-1999, 2000=≥2000.
_YEAR_BANDS = [1990, 1991, 1994, 1997, 2000]

_PES_TABLES = None   # lazy-loaded ≥12t matrix (only heavy trucks need it)


def _pes_tables():
    global _PES_TABLES
    if _PES_TABLES is None:
        path = _os.path.join(_os.path.dirname(__file__), "iuc_pesados_2026.json")
        with open(path, encoding="utf-8") as fh:
            _PES_TABLES = _json.load(fh)
    return _PES_TABLES


def _bracket_lower(key: str) -> int:
    """Lower bound (kg) encoded in a weight-bracket key: 'less_15000'→0 (first bracket),
    '18000_plus'→18000, '13000_14999'→13000, bare '12000'→12000."""
    if key.startswith("less_"):
        return 0
    if key.endswith("_plus"):
        return int(key[:-5])
    if "_" in key:
        return int(key.split("_")[0])
    return int(key)


def _pick_weight_key(brackets: dict, peso: int) -> str:
    """Highest bracket whose lower bound ≤ peso (brackets are contiguous by construction)."""
    best, best_lo = None, -1
    for k in brackets:
        lo = _bracket_lower(k)
        if lo <= peso and lo > best_lo:
            best, best_lo = k, lo
    return best or min(brackets, key=_bracket_lower)


def _year_band_key(year) -> str:
    y = int(year or 2000)
    band = _YEAR_BANDS[0]
    for b in _YEAR_BANDS:
        if y >= b:
            band = b
    return str(band)


def compute_cd(peso_bruto: int, year: int | None, util: str = "particular",
               axles: int = 2, suspension: str = "pneumatica", config: str = "rigido",
               tractor_axles: int = 2, trailer_axles: int = 1,
               regiao_autonoma: bool = False, fuel: str = "diesel") -> dict:
    """Annual IUC (€) for a goods vehicle — Categoria C (particular) or D (público/aluguer).
    Peso-bruto based, no cc/CO2. <12t → single weight bracket; ≥12t → peso×eixos×suspensão×ano
    (config='articulado' uses the tractor+trailer axle sub-table). electric is NOT exempt here
    (C/D isenção is by use, not fuel). regiao_autonoma applies the −50% (art. 5º nº8)."""
    peso = max(int(peso_bruto or 0), 0)
    publico = (util or "particular").lower() in ("publico", "público", "aluguer", "d")
    cat_key = "CATEGORIA_D" if publico else "CATEGORIA_C"
    cat_letter = "D" if publico else "C"
    detail = {}

    if peso < 12000:
        leves = CAT_D_LEVES if publico else CAT_C_LEVES
        base = next((v for hi, v in leves if peso <= hi), leves[-1][1])
        detail = {"escalao": "leves_<12t", "peso_bruto": peso}
    else:
        T = _pes_tables()[cat_key]
        band = _year_band_key(year)
        sus = "pneumatica" if str(suspension).startswith("pneu") else "outro"
        if str(config).startswith("artic"):
            cfg = f"{int(tractor_axles)}_{int(trailer_axles)}"
            grp = T["ARTICULADOS"].get(cfg)
            if grp is None:
                return {"iuc": None, "exempt": False, "category": cat_letter,
                        "note": f"Configuração articulada {cfg} não reconhecida — verifique eixos."}
            detail = {"grupo": "articulados", "config": cfg}
        else:
            grp = T["PESADOS"].get(str(int(axles)))
            if grp is None:
                return {"iuc": None, "exempt": False, "category": cat_letter,
                        "note": "Nº de eixos inválido (2, 3 ou 4)."}
            detail = {"grupo": "rigido", "eixos": int(axles)}
        wkey = _pick_weight_key(grp, peso)
        base = grp[wkey][band][sus]
        detail.update({"escalao_peso": wkey, "banda_ano": band, "suspensao": sus,
                       "peso_bruto": peso})

    iuc = base * (REGIAO_AUTONOMA_DESCONTO if regiao_autonoma else 1.0)
    iuc = round(iuc, 2)
    if iuc < MINIMO_COBRANCA:
        return {"iuc": 0.0, "exempt": True, "category": cat_letter,
                "note": f"IUC calculado ({iuc:.2f} €) inferior ao mínimo de "
                        f"{MINIMO_COBRANCA:.0f} € — não há lugar a liquidação (art. 16º nº6).",
                "base": base, **detail}
    return {"iuc": iuc, "exempt": False, "category": cat_letter, "note": None,
            "base": round(base, 2), "regiao_autonoma": bool(regiao_autonoma),
            "taxa_cilindrada": None, "taxa_co2": 0.0, "coef": 1.0,
            "diesel_adic": 0.0, "co2_adic": 0.0, **detail}


# ── Unified IUC router — maps a vehicle_type to the correct category ──────────────────────
# Goods vehicles (any weight) are Categoria C/D by peso bruto — NEVER Categoria B (art. 2º).
# Buses (pesados de passageiros) are não sujeitos. Passenger/moto keep their existing paths.
LIGEIROS_MERCADORIAS = {"commercial_100", "van_10", "commercial_15", "commercial_50"}
PESADOS_MERCADORIAS = {"pesados_mercadorias"}
NAO_SUJEITO_IUC = {"pesados_passageiros", "autocarro"}   # buses have no IUC category


def compute_iuc(vehicle_type, cc, co2, fuel, year, *, peso_bruto=0, utilizacao="particular",
                axles=2, suspension="pneumatica", config="rigido", tractor_axles=2,
                trailer_axles=1, regiao_autonoma=False, month=None):
    """Dispatch to the correct IUC category by vehicle_type. Goods vehicles → Cat C/D (weight);
    buses → não sujeito; passenger → Cat A/B (cc+CO2); moto → Cat E."""
    vt = (vehicle_type or "passenger").lower()
    if vt in NAO_SUJEITO_IUC:
        return {"iuc": None, "exempt": True, "not_subject": True, "category": None,
                "note": "Pesado de passageiros (autocarro) — não sujeito a IUC (não consta das "
                        "categorias do art. 2º CIUC)."}
    if vt in LIGEIROS_MERCADORIAS or vt in PESADOS_MERCADORIAS:
        if int(peso_bruto or 0) <= 0:
            # Weight drives every goods-vehicle bracket — without it we cannot compute (like cc
            # for passenger). Signal the UI to prompt rather than guessing the lowest bracket.
            return {"iuc": None, "need_peso": True, "category": "C/D",
                    "note": "Indique o peso bruto (kg) para calcular o IUC (Cat. C/D)."}
        return compute_cd(peso_bruto, year, util=utilizacao, axles=axles, suspension=suspension,
                          config=config, tractor_axles=tractor_axles, trailer_axles=trailer_axles,
                          regiao_autonoma=regiao_autonoma, fuel=fuel)
    if vt == "autocaravana":
        # Ligeira (≤3500 kg): standard AT practice taxes it as Categoria B (cc+CO2) — CIUC art 2º
        # has no autocaravana entry, and Cat B references CISV 2.1 a)/d) (not e), so this is
        # practitioner treatment, not a clean statutory fit. Pesada (>3500 kg) hits the same gap
        # as buses (no mercadorias category either) → flag for AT confirmation rather than guess.
        r = compute(cc, co2, fuel, year, vehicle_type="passenger", month=month)
        if int(peso_bruto or 0) > 3500:
            r = dict(r, verify_at=True,
                     note="Autocaravana pesada (>3500 kg) — sem categoria de IUC estatutária "
                          "clara; confirme o enquadramento com a AT.")
        return r
    # passenger / misto≤2500 / motorcycle → existing A/B/E core (misto>2500 is out of the
    # offered types; if ever added it must route to compute_cd by peso bruto — art 2º c)/d).
    return compute(cc, co2, fuel, year, vehicle_type=vt, month=month)
