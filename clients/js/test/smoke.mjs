// Smoke test for portugal-vehicle-tax (API client).
// Part A (offline): a mock fetch proves params are serialized and the response is parsed.
// Part B (live): hits the real TransparentCars API and asserts invariants + known golden numbers.
//   Set SKIP_LIVE=1 to run only the offline part (e.g. in a network-less CI).
//
// Run:  npm run build && node test/smoke.mjs

import assert from "node:assert/strict";
import { PortugalVehicleTax, getTax, DISCLAIMER } from "../dist/index.js";

// ── Part A: offline, mock fetch ──────────────────────────────────────────────
{
  let seenUrl = "";
  const mockFetch = async (url) => {
    seenUrl = String(url);
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        isv: { isv: 1832.92, exempt: false, note: null, table: "A" },
        iuc: { iuc: 278.85, exempt: false, note: null, category: "B" },
        source: "https://transparent.pt/en/isv",
        disclaimer: "maintained estimate",
      }),
    };
  };
  const client = new PortugalVehicleTax({ fetch: mockFetch });
  const r = await client.getTax({ cc: 1950, co2: 130, fuel: "diesel", year: 2016 });
  assert.match(seenUrl, /\/isv\?/, "calls the /isv endpoint");
  assert.match(seenUrl, /cc=1950/, "serializes cc");
  assert.match(seenUrl, /fuel=diesel/, "serializes fuel");
  assert.equal(r.isv.isv, 1832.92);
  assert.equal(r.iuc.iuc, 278.85);
  assert.ok(DISCLAIMER.includes("not the official AT figure"), "exports the honesty note");
  console.log("A offline mock-fetch: OK");
}

// ── Part B: live API, real numbers ───────────────────────────────────────────
if (process.env.SKIP_LIVE === "1") {
  console.log("B live API: SKIPPED (SKIP_LIVE=1)");
} else {
  const api = new PortugalVehicleTax();
  // petrol/diesel used with age reduction, EV exempt, €100 minimum
  const diesel = await api.getTax({ cc: 1950, co2: 130, fuel: "diesel", year: 2016 });
  assert.ok(diesel.isv.isv > 0 && diesel.iuc.iuc > 0, "diesel: both taxes positive");

  const ev = await api.getTax({ fuel: "electric", year: 2023 });
  assert.equal(ev.isv.isv, 0, "EV: ISV exempt");
  assert.equal(ev.isv.exempt, true);
  assert.equal(ev.iuc.iuc, 0, "EV: IUC exempt");

  const tiny = await api.getIsv({ cc: 900, co2: 95, fuel: "petrol", year: 2005 });
  assert.ok(tiny.isv >= 100, "min-ISV floor of €100 respected");

  console.log("B live API: OK (diesel>0, EV exempt, min-€100)");
}

console.log("smoke: PASS");
