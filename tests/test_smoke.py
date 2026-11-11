"""Smoke tests for the calculators + the reference API.

The calculator tests need NO dependencies (pure stdlib). The API tests are skipped
automatically if fastapi/httpx aren't installed, so `pytest` works in a bare env too.

Run:  pytest -q
"""
import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import isv, iuc  # noqa: E402


def _age(year, month=6):
    now = dt.datetime.now(dt.timezone.utc)
    return max(0.0, (now - dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)).days / 365.25)


# ── Calculators (dependency-free) ────────────────────────────────────────────────────────────────
def test_isv_diesel_used_import_is_positive():
    r = isv.compute_isv("passenger", 1950, 130, "diesel", _age(2016), 2016,
                        from_eu=True, used=True, particulas=True)
    assert isinstance(r, dict) and r["isv"] > 0 and r["table"] == "A"


def test_iuc_diesel_2016_is_positive():
    r = iuc.compute(1950, 130, "diesel", 2016, vehicle_type="passenger")
    assert r["iuc"] > 0 and r["category"] == "B"


def test_electric_is_exempt_both_taxes():
    isv_ev = isv.compute_isv("passenger", 0, 0, "electric", _age(2023), 2023)
    iuc_ev = iuc.compute(0, 0, "electric", 2023, vehicle_type="passenger")
    assert isv_ev["isv"] == 0.0
    assert iuc_ev["iuc"] == 0.0 and iuc_ev.get("exempt") is True


def test_deterministic_same_input_same_output():
    a = isv.compute_isv("passenger", 1600, 120, "petrol", _age(2018), 2018)
    b = isv.compute_isv("passenger", 1600, 120, "petrol", _age(2018), 2018)
    assert a == b


# ── Reference API (skipped if fastapi/httpx absent) ──────────────────────────────────────────────
fastapi = pytest.importorskip("fastapi", reason="install requirements.txt to test the API")
pytest.importorskip("httpx", reason="install requirements.txt to test the API")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import app
    return TestClient(app.app)


def test_isv_endpoint_returns_both_taxes_and_attribution(client):
    r = client.get("/isv", params=dict(cc=1950, co2=130, fuel="diesel", year=2016))
    assert r.status_code == 200
    j = r.json()
    assert j["isv"]["isv"] > 0 and j["iuc"]["iuc"] > 0
    assert j["source"].startswith("http") and "estimate" in j["disclaimer"].lower()
    assert r.headers["Cache-Control"].startswith("public")


def test_isv_endpoint_caches(client):
    p = dict(cc=1400, co2=110, fuel="petrol", year=2019)
    assert client.get("/isv", params=p).headers["X-Cache"] == "MISS"
    assert client.get("/isv", params=p).headers["X-Cache"] == "HIT"


def test_iuc_endpoint(client):
    r = client.get("/iuc", params=dict(cc=1950, co2=130, fuel="diesel", year=2016))
    assert r.status_code == 200 and r.json()["iuc"]["iuc"] > 0
