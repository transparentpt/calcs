"""
TransparentCars — Portugal car-tax public API (open-source reference server).

A tiny, dependency-light FastAPI app that exposes the Portuguese vehicle-tax
calculators (ISV import tax + IUC annual road tax) plus the make/model vocabulary,
as a key-free JSON API. This is the same public contract served at
https://transparent.pt/api/public — published so anyone can self-host, fork, or audit it.

Design goals (match the hosted service):
  * No auth, no keys, no state, no PII — vehicle params in, numbers out.
  * Deterministic → aggressively cacheable (param-hash cache + Cache-Control).
  * Abuse-bounded → generous per-IP rate limit, 429 + Retry-After.
  * Honest → the figures are a MAINTAINED ESTIMATE, not the official AT number.

Run:
    pip install -r requirements.txt
    uvicorn app:app --host 0.0.0.0 --port 8080
Then:
    curl "http://localhost:8080/isv?cc=1950&co2=130&fuel=diesel&year=2016"
    curl "http://localhost:8080/iuc?cc=1950&co2=130&fuel=diesel&year=2016"

License: code MIT. See LICENSE and README.md for the data/accuracy disclaimer.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import isv as isv_mod
from src import iuc as iuc_mod

# ── Config (all env-tunable; safe generous defaults) ────────────────────────────────────────────
ATTRIBUTION = os.environ.get("ATTRIBUTION_URL", "https://transparent.pt/en/isv")
CALC_RATE_MAX = int(os.environ.get("CALC_RATE_MAX", "60"))       # requests…
CALC_RATE_WIN = int(os.environ.get("CALC_RATE_WIN", "60"))       # …per this many seconds
CALC_CACHE_TTL = int(os.environ.get("CALC_CACHE_TTL", "3600"))   # seconds
CALC_CACHE_MAX = int(os.environ.get("CALC_CACHE_MAX", "5000"))   # entries

app = FastAPI(
    title="TransparentCars — Portugal car-tax API",
    version="1.0.0",
    description="Key-free ISV (import tax) + IUC (road tax) estimates for Portugal. "
                "Maintained estimate, not the official AT figure.",
    docs_url="/docs", redoc_url="/redoc",
)
# Calc endpoints carry no cookies and no PII → wildcard CORS is safe and enables embedding.
# NEVER combine allow_origins=["*"] with allow_credentials=True.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["GET"], allow_headers=["Content-Type"])


# ── Per-IP sliding-window rate limiter (in-memory; single process) ───────────────────────────────
_hits: dict[str, list[float]] = {}


def _client_ip(req: Request) -> str:
    # Trust a reverse-proxy-set X-Real-IP if present; else right-most XFF (proxy-appended); else peer.
    real = req.headers.get("x-real-ip", "").strip()
    if real:
        return real
    fwd = req.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return req.client.host if req.client else "?"


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    if len(_hits) > 10000:                       # bound memory: drop keys with no live hits
        for k in [k for k, v in _hits.items() if all(now - t >= CALC_RATE_WIN for t in v)]:
            _hits.pop(k, None)
    win = [t for t in _hits.get(ip, []) if now - t < CALC_RATE_WIN]
    if len(win) >= CALC_RATE_MAX:
        _hits[ip] = win
        return False
    win.append(now)
    _hits[ip] = win
    return True


def _rate_limited() -> JSONResponse:
    return JSONResponse({"detail": "rate limited"}, status_code=429,
                        headers={"Retry-After": str(CALC_RATE_WIN)})


# ── Deterministic param-hash response cache ──────────────────────────────────────────────────────
_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(params: dict) -> str:
    canon = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def _cache_get(key: str):
    hit = _cache.get(key)
    if not hit:
        return None
    ts, val = hit
    if time.monotonic() - ts > CALC_CACHE_TTL:
        _cache.pop(key, None)
        return None
    return val


def _cache_put(key: str, val: dict):
    if len(_cache) >= CALC_CACHE_MAX:            # crude LRU-ish: drop oldest ~10%
        for k in sorted(_cache, key=lambda k: _cache[k][0])[: CALC_CACHE_MAX // 10]:
            _cache.pop(k, None)
    _cache[key] = (time.monotonic(), val)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _age_years(year: int | None, month: int) -> float:
    if year and 1950 <= year <= _now().year:
        month = min(max(month, 1), 12)
        return max(0.0, (_now() - dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)).days / 365.25)
    return 0.0


def _ok(result: dict, cache_state: str) -> JSONResponse:
    result = {**result, "source": ATTRIBUTION,
              "disclaimer": "Maintained estimate of the Portuguese tax — not the official AT figure."}
    return JSONResponse(result, headers={"Cache-Control": f"public, max-age={CALC_CACHE_TTL}",
                                         "X-Cache": cache_state})


# ── Endpoints ────────────────────────────────────────────────────────────────────────────────────
@app.get("/isv")
async def get_isv(request: Request, cc: int = 0, co2: int = 0, fuel: str = "petrol",
                  year: int | None = None, month: int = 6, from_eu: bool = True,
                  range_km: int = 0, used: bool = True,
                  vehicle_type: str = "passenger", particulas: bool = True):
    """Estimate ISV (one-off import tax) AND IUC (annual road tax) in one call.

    Mirrors the hosted transparent.pt/api/public/isv contract → the published OpenAPI spec
    describes both this and /iuc.
    """
    if not _rate_ok(_client_ip(request)):
        return _rate_limited()
    cc = max(min(cc, 10000), 0)
    co2 = max(min(co2, 1000), 0)
    yr = year if (year and 1950 <= year <= _now().year) else None
    params = {"cc": cc, "co2": co2, "fuel": (fuel or "petrol")[:20], "year": yr,
              "month": min(max(month, 1), 12), "from_eu": bool(from_eu),
              "range_km": max(min(range_km, 2000), 0), "used": bool(used),
              "vehicle_type": (vehicle_type or "passenger")[:20], "particulas": bool(particulas),
              "_ep": "isv"}
    key = _cache_key(params)
    cached = _cache_get(key)
    if cached is not None:
        return _ok(cached, "HIT")
    age = _age_years(yr, month)
    isv_val = isv_mod.compute_isv(vehicle_type, cc, co2, fuel, age, yr,
                                  from_eu=params["from_eu"], phev_range_km=params["range_km"],
                                  used=params["used"], particulas=params["particulas"])
    iuc_val = iuc_mod.compute(cc, co2, fuel, yr, vehicle_type=vehicle_type)
    result = {"isv": isv_val, "iuc": iuc_val}
    _cache_put(key, result)
    return _ok(result, "MISS")


@app.get("/iuc")
async def get_iuc(request: Request, cc: int = 0, co2: int = 0, fuel: str = "petrol",
                  year: int | None = None, vehicle_type: str = "passenger"):
    """Estimate IUC (annual road tax) only — clean single-purpose endpoint."""
    if not _rate_ok(_client_ip(request)):
        return _rate_limited()
    cc = max(min(cc, 10000), 0)
    co2 = max(min(co2, 1000), 0)
    yr = year if (year and 1950 <= year <= _now().year) else None
    params = {"cc": cc, "co2": co2, "fuel": (fuel or "petrol")[:20], "year": yr,
              "vehicle_type": (vehicle_type or "passenger")[:20], "_ep": "iuc"}
    key = _cache_key(params)
    cached = _cache_get(key)
    if cached is not None:
        return _ok(cached, "HIT")
    result = {"iuc": iuc_mod.compute(cc, co2, fuel, yr, vehicle_type=vehicle_type)}
    _cache_put(key, result)
    return _ok(result, "MISS")


@app.get("/health")
async def health():
    return {"ok": True}
