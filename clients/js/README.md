# portugal-vehicle-tax (JS/TS)

TypeScript client for the **TransparentCars** Portuguese vehicle-tax API — **ISV** (*Imposto Sobre
Veículos*, the one-off import tax) and **IUC** (*Imposto Único de Circulação*, the annual road
tax). One call returns both.

This package is a **thin, typed HTTP client** — it calls the public, key-free TransparentCars API
(`https://transparent.pt/api/public/isv`). It does **not** re-implement the tax math; the numbers
come from the maintained calculators behind that API. Homepage: **[transparent.pt](https://transparent.pt)**.

> **A maintained estimate, cross-checked against the official AT simulator; not the official
> AT figure.** Not a substitute for the AT simulator or a licensed despachante. Tax tables
> change every year; verify before you rely on a euro amount. The verbatim note is exported as
> `DISCLAIMER`.

## Install

```bash
npm install portugal-vehicle-tax
```

Node 18+ (uses the global `fetch`), or any browser, or pass your own `fetch`.

## Usage

```ts
import { PortugalVehicleTax } from "portugal-vehicle-tax";

const tax = new PortugalVehicleTax();

// ISV + IUC in one call
const r = await tax.getTax({ cc: 1950, co2: 130, fuel: "diesel", year: 2016 });
console.log(r.isv.isv); // 1832.92  (import tax, €)
console.log(r.iuc.iuc); // 278.85   (annual road tax, €)

// Just one of them
await tax.getIsv({ cc: 1600, co2: 120, fuel: "petrol", year: 2018 });
await tax.getIuc({ cc: 1600, co2: 120, fuel: "petrol", year: 2018 });

// Electric → exempt from both (isv 0, iuc 0, exempt: true)
await tax.getTax({ fuel: "electric", year: 2023 });
```

One-shot helper, no client:

```ts
import { getTax } from "portugal-vehicle-tax";
const r = await getTax({ cc: 1400, co2: 30, fuel: "phev", year: 2024, range_km: 60 });
```

### Query fields (`TaxQuery`)

`cc`, `co2`, `fuel` (`petrol｜diesel｜electric｜phev｜hybrid｜lpg`), `year`, `month`, `from_eu`,
`range_km`, `used`, `vehicle_type` (`passenger｜van_10｜commercial_15/50/100｜motorcycle｜
autocaravana｜pesados_mercadorias｜pesados_passageiros`), `particulas`. All optional.

### Options

```ts
new PortugalVehicleTax({
  baseUrl: "https://transparent.pt/api/public", // override to self-host the OSS API
  timeoutMs: 8000,
  fetch: myFetch,                             // custom fetch for tests / edge runtimes
});
```

Fully typed: `TaxResult`, `IsvResult`, `IucResult`, `TaxQuery`, `Fuel`, `VehicleType`.

## Test

```bash
npm run build && npm test          # offline mock-fetch + live-API invariants
SKIP_LIVE=1 npm test               # offline part only (no network)
```

## Related

- **Python native library** (offline, no API): [`portugal-vehicle-tax` on PyPI](https://pypi.org/project/portugal-vehicle-tax/)
- **PHP SDK:** [`transparentpt/portugal-vehicle-tax` on Packagist](https://packagist.org/packages/transparentpt/portugal-vehicle-tax)
- **API docs:** https://transparent.pt/en/api · **Source:** https://github.com/transparentpt/calcs

MIT © TransparentCars
