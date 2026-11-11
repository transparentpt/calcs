<img src="https://raw.githubusercontent.com/transparentpt/mcp/main/assets/wordmark.png" alt="TransparentCars" width="200" align="right" />

# Portugal car-tax calculators — ISV & IUC

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![OpenAPI 3.1](https://img.shields.io/badge/OpenAPI-3.1-blue.svg)](./openapi.yaml)
[![PyPI](https://img.shields.io/pypi/v/portugal-vehicle-tax.svg)](https://pypi.org/project/portugal-vehicle-tax/)
[![npm](https://img.shields.io/npm/v/portugal-vehicle-tax.svg)](https://www.npmjs.com/package/portugal-vehicle-tax)
[![Packagist](https://img.shields.io/packagist/v/transparentpt/portugal-vehicle-tax.svg)](https://packagist.org/packages/transparentpt/portugal-vehicle-tax)

Open-source calculators for the two Portuguese vehicle taxes, plus a tiny key-free HTTP API and
installable packages for Python, JavaScript/TypeScript and PHP:

- **ISV** — *Imposto Sobre Veículos*, the one-off import/registration tax (Tabela A/B/C/D, motorhomes, motorcycles).
- **IUC** — *Imposto Único de Circulação*, the annual road tax (Categoria A / B / C / D / E).

Maintained by **[TransparentCars](https://transparent.pt)** and used in production behind the public API at `https://transparent.pt/api/public` and the [TransparentCars MCP server](https://github.com/transparentpt/mcp).

> **A maintained estimate, cross-checked against the official AT simulator; not the official AT figure.** These are a *maintained estimate*, cross-checked periodically against the official Autoridade Tributária (AT) simulator and public tax tables — **not** the official AT number and not a substitute for the AT simulator or a licensed despachante. Tax tables change; verify before you rely on a euro amount.

## Coverage

| Tax | Categories | Basis |
|---|---|---|
| **ISV** | Tabela A (passenger), B (light commercial / mixed), C (motorcycles), autocaravanas, **pesados** (não sujeito) | cc + CO₂ (WLTP/NEDC), age reduction (Tabela D), diesel surcharge, PHEV reduction, €100 minimum |
| **IUC** | A (<2007), B (≥2007), E (motorcycles), **C / D (goods vehicles, incl. ≥12 t)** | cc + CO₂ for cars; **gross weight × axles × suspension × year** for goods vehicles |

Electric vehicles return `0.0` / `exempt: True` for both.

## Install a package

```bash
pip install portugal-vehicle-tax                    # Python — native, offline, zero deps
npm install portugal-vehicle-tax                    # JS/TS — API client
composer require transparentpt/portugal-vehicle-tax     # PHP — API client
```

The clients live in this repo: [`clients/js`](./clients/js) and [`clients/php`](./clients/php).
The Python package mirrors [`src/`](./src). The JS and PHP packages are thin, honest clients of
the public API (they don't re-implement the tax math — one source of truth).

## Use it as a library (Python, zero dependencies)

`src/isv.py` and `src/iuc.py` are pure Python (stdlib only) — copy them in or import:

```python
from src import isv, iuc

# 2016 diesel, 1950 cc, 130 g/km CO2, used EU import
isv_result = isv.compute_isv("passenger", cc=1950, co2=130, fuel="diesel",
                             age_years=10.2, year=2016, from_eu=True, used=True)
# {'isv': 1832.92, 'exempt': False, 'table': 'A', ...}

iuc_result = iuc.compute(cc=1950, co2=130, fuel="diesel", year=2016)
# {'iuc': 278.85, 'category': 'B', 'taxa_cilindrada': 127.35, 'taxa_co2': 97.63, ...}

# Goods vehicle (Categoria C/D — by gross weight, not cc/CO2)
iuc.compute_iuc("pesados_mercadorias", 0, 0, "diesel", 2019, peso_bruto=18000, axles=2)
```

## Use it as an API

```bash
pip install -r requirements.txt
uvicorn app:app --port 8080
```

```bash
# ISV + IUC in one call
curl "http://localhost:8080/isv?cc=1950&co2=130&fuel=diesel&year=2016"
```

The hosted instance (same contract) is live and key-free:

```bash
curl "https://transparent.pt/api/public/isv?cc=1950&co2=130&fuel=diesel&year=2016"
```

Full request/response schema: [`openapi.yaml`](./openapi.yaml). Interactive docs at `/docs` when you run the app.

### Parameters (`/isv`)

| Param | Type | Default | Notes |
|---|---|---|---|
| `cc` | int | 0 | Engine displacement (cm³) |
| `co2` | int | 0 | CO₂ g/km (WLTP/NEDC handled by registration year) |
| `fuel` | string | `petrol` | `petrol` \| `diesel` \| `electric` \| `phev` \| `hybrid` \| `lpg` |
| `year` | int | — | First-registration year (drives age reduction + NEDC/WLTP + IUC categoria) |
| `month` | int | 6 | First-registration month |
| `from_eu` | bool | true | EU import (affects age-reduction eligibility) |
| `range_km` | int | 0 | Electric range — a PHEV needs ≥50 km (+ low CO₂) for the 75% reduction |
| `used` | bool | true | `false` (novo) → no age reduction |
| `vehicle_type` | string | `passenger` | `passenger` \| `van_10` \| `commercial_15/50/100` \| `motorcycle` \| `autocaravana` \| `pesados_mercadorias` \| `pesados_passageiros` |
| `particulas` | bool | true | Diesel particle surcharge (≥0.001 g/km) |

`/iuc` takes `cc, co2, fuel, year, vehicle_type`.

## Tests

```bash
pytest -q                        # or: python tests/test_calc_golden.py
```

`tests/test_calc_golden.py` freezes a golden case table (petrol, diesel with age reduction,
electric-exempt, the €100 minimum, PHEV reduction, Categoria C/D goods vehicle) so any drift in
the tables fails. `tests/test_smoke.py` covers the calculators + the reference API.

## Design

- **No auth, no keys, no PII, no state** — vehicle params in, numbers out.
- **Deterministic** → the reference API caches by param hash and sends `Cache-Control`.
- **Abuse-bounded** → generous per-IP rate limit (default 60/min → `429` + `Retry-After`), wildcard CORS (safe: no cookies/PII). Env-tunable: `CALC_RATE_MAX`, `CALC_RATE_WIN`, `CALC_CACHE_TTL`.
- Every response carries a `source` attribution link back to transparent.pt.

## Related

- **Hosted API + docs:** https://transparent.pt/en/api
- **MCP server:** [transparentpt/mcp](https://github.com/transparentpt/mcp) — AI assistants call these calculators + live stock over the Model Context Protocol.
- **WordPress plugin:** [transparentpt/wp](https://github.com/transparentpt/wp) — TransparentCars Calculator.

## Contributing

Tax tables change every year. PRs that update a bracket/coefficient with a link to the official AT source are very welcome. `pytest -q` runs the (dependency-free) calculator tests.

MIT © TransparentCars
