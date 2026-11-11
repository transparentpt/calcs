# transparentpt/portugal-vehicle-tax (PHP)

PHP client for the **TransparentCars** Portuguese vehicle-tax API — **ISV** (*Imposto Sobre
Veículos*, the one-off import tax) and **IUC** (*Imposto Único de Circulação*, the annual road
tax). One call returns both.

A **thin, dependency-free HTTP client** (cURL, with an `allow_url_fopen` fallback). It does
**not** re-implement the tax math — it calls the public, key-free TransparentCars API
(`https://transparent.pt/api/public/isv`). Homepage: **[transparent.pt](https://transparent.pt)**.

> **A maintained estimate, cross-checked against the official AT simulator; not the official
> AT figure.** Not a substitute for the AT simulator or a licensed despachante. Tax tables
> change every year; verify before you rely on a euro amount. Exported as `Client::DISCLAIMER`.

## Install

```bash
composer require transparentpt/portugal-vehicle-tax
```

PHP 7.4+. No runtime dependencies.

## Usage

```php
use TransparentCars\VehicleTax\Client;

$tax = new Client();

// ISV + IUC in one call
$r = $tax->getTax(['cc' => 1950, 'co2' => 130, 'fuel' => 'diesel', 'year' => 2016]);
echo $r['isv']['isv']; // 1832.92  (import tax, €)
echo $r['iuc']['iuc']; // 278.85   (annual road tax, €)

// Just one of them
$tax->getIsv(['cc' => 1600, 'co2' => 120, 'fuel' => 'petrol', 'year' => 2018]);
$tax->getIuc(['cc' => 1600, 'co2' => 120, 'fuel' => 'petrol', 'year' => 2018]);

// Electric → exempt from both
$tax->getTax(['fuel' => 'electric', 'year' => 2023]); // isv 0, iuc 0, exempt: true
```

### Query keys

`cc`, `co2`, `fuel` (`petrol｜diesel｜electric｜phev｜hybrid｜lpg`), `year`, `month`, `from_eu`,
`range_km`, `used`, `vehicle_type` (`passenger｜van_10｜commercial_15/50/100｜motorcycle｜
autocaravana｜pesados_mercadorias｜pesados_passageiros`), `particulas`. All optional. Booleans
are serialized as `true`/`false`.

### Options

```php
new Client('https://transparent.pt/api/public', 8); // baseUrl (self-host the OSS API), timeout(s)
```

## Test

```bash
composer test          # or: php tests/SmokeTest.php
SKIP_LIVE=1 php tests/SmokeTest.php   # offline only (no network)
```

## Related

- **Python native library** (offline, no API): [`portugal-vehicle-tax` on PyPI](https://pypi.org/project/portugal-vehicle-tax/)
- **JS/TS SDK:** [`portugal-vehicle-tax` on npm](https://www.npmjs.com/package/portugal-vehicle-tax)
- **WordPress plugin:** [transparentpt/wp](https://github.com/transparentpt/wp) — TransparentCars Calculator
- **API docs:** https://transparent.pt/en/api · **Source:** https://github.com/transparentpt/calcs

MIT © TransparentCars
