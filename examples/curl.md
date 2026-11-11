# Examples

Hosted (key-free) — swap the base for `http://localhost:8080` when self-hosting.

```bash
BASE=https://transparent.pt/api/public

# 2016 diesel, 1950 cc, 130 g/km CO2, used EU import → ISV + IUC
curl "$BASE/isv?cc=1950&co2=130&fuel=diesel&year=2016"

# Petrol, brand new (no age reduction)
curl "$BASE/isv?cc=1400&co2=120&fuel=petrol&year=2025&used=false"

# Pure electric → exempt from both
curl "$BASE/isv?cc=0&co2=0&fuel=electric&year=2024"

# PHEV with 60 km electric range (qualifies for the 75% reduction)
curl "$BASE/isv?cc=1600&co2=40&fuel=phev&year=2023&range_km=60"

# Motorhome (autocaravana)
curl "$BASE/isv?cc=2200&co2=190&fuel=diesel&year=2018&vehicle_type=autocaravana"

# Motorcycle
curl "$BASE/isv?cc=650&fuel=petrol&year=2020&vehicle_type=motorcycle"

# IUC only (self-hosted route; hosted returns it inside /isv)
curl "http://localhost:8080/iuc?cc=1950&co2=130&fuel=diesel&year=2016"
```

Python (library, no HTTP):

```python
from src import isv, iuc
print(isv.compute_isv("passenger", cc=1950, co2=130, fuel="diesel", age_years=9.1, year=2016))
print(iuc.compute(cc=1950, co2=130, fuel="diesel", year=2016))
```
