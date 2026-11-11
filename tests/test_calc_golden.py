"""Golden self-check for the ISV/IUC calculators (dependency-free).

Frozen against the canonical TransparentCars logic, itself cross-checked vs the official AT
simulator. age_years is PINNED so the euro amounts are deterministic. Any drift fails.
Covers: petrol, diesel with age reduction, electric-exempt, the €100 minimum, PHEV
reduction, and a Categoria C/D heavy-goods case (needs src/iuc_pesados_2026.json).

Run:  pytest -q   (or plain: python tests/test_calc_golden.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import isv, iuc  # noqa: E402

ISV_CASES = [
    # (label, kwargs, expected_isv, exempt)
    ("diesel_used_import",
     dict(category="passenger", cc=1950, co2=130, fuel="diesel", age_years=10.2, year=2016,
          from_eu=True, used=True, particulas=True), 1832.92, False),
    ("petrol_used_import",
     dict(category="passenger", cc=1600, co2=120, fuel="petrol", age_years=8.2, year=2018,
          from_eu=True, used=True), 955.32, False),
    ("electric_exempt",
     dict(category="passenger", cc=0, co2=0, fuel="electric", age_years=3.2, year=2023), 0.0, True),
    ("min_isv_100",
     dict(category="passenger", cc=900, co2=95, fuel="petrol", age_years=21.2, year=2005,
          from_eu=True, used=True), 100.0, False),
    ("phev_reduction",
     dict(category="passenger", cc=1400, co2=30, fuel="phev", age_years=2.2, year=2024,
          phev_range_km=60, from_eu=True, used=True), 291.19, False),  # half-up per AT breakdown (was 291.18 with float rounding)
]

IUC_CASES = [
    ("diesel_2016", dict(cc=1950, co2=130, fuel="diesel", year=2016), 278.85),
    ("petrol_2018", dict(cc=1600, co2=120, fuel="petrol", year=2018), 148.22),
    ("electric_exempt", dict(cc=0, co2=0, fuel="electric", year=2023), 0.0),
    ("cat_a_pre2007", dict(cc=900, co2=95, fuel="petrol", year=2005), 19.90),
]


def test_isv_golden():
    for label, kw, exp, exempt in ISV_CASES:
        r = isv.compute_isv(**kw)
        assert r["isv"] == exp, f"{label}: ISV {r['isv']} != {exp}"
        assert bool(r.get("exempt")) == exempt, f"{label}: exempt mismatch"


def test_iuc_golden():
    for label, kw, exp in IUC_CASES:
        r = iuc.compute(**kw)
        assert r["iuc"] == exp, f"{label}: IUC {r['iuc']} != {exp}"


def test_iuc_cat_cd_pesados():
    # Heavy goods vehicle, ≥12t — Categoria C by gross weight (uses the baked pesados JSON).
    r = iuc.compute_iuc("pesados_mercadorias", 0, 0, "diesel", 2019, peso_bruto=18000, axles=2)
    assert r["category"] == "C" and isinstance(r["iuc"], (int, float)) and r["iuc"] > 0


def test_min_isv_floor():
    r = isv.compute_isv("passenger", 900, 95, "petrol", 21.2, 2005)
    assert r["isv"] >= 100.0 and r["min_isv_applied"] is True


if __name__ == "__main__":
    test_isv_golden()
    test_iuc_golden()
    test_iuc_cat_cd_pesados()
    test_min_isv_floor()
    print(f"OK — {len(ISV_CASES)} ISV + {len(IUC_CASES)} IUC golden cases + Cat C/D + min-ISV passed")
