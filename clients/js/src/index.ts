/**
 * portugal-vehicle-tax — TypeScript client for the TransparentCars Portuguese vehicle-tax API.
 *
 * This is a thin, typed HTTP client. It does NOT re-implement the tax math — it calls the
 * public, key-free TransparentCars API (https://transparent.pt/api/public/isv), which returns BOTH
 * the ISV (import tax) and the IUC (annual road tax) for a vehicle.
 *
 * The numbers are a maintained estimate, cross-checked against the official AT simulator;
 * not the official AT figure. See https://transparent.pt.
 */

export type Fuel = "petrol" | "diesel" | "electric" | "phev" | "hybrid" | "lpg";

export type VehicleType =
  | "passenger"
  | "van_10"
  | "commercial_15"
  | "commercial_50"
  | "commercial_100"
  | "motorcycle"
  | "autocaravana"
  | "pesados_mercadorias"
  | "pesados_passageiros";

export interface TaxQuery {
  /** Engine displacement, cm³ */
  cc?: number;
  /** CO₂ g/km (WLTP/NEDC auto-selected by year) */
  co2?: number;
  fuel?: Fuel;
  /** First-registration year */
  year?: number;
  /** First-registration month (1–12), default 6 */
  month?: number;
  /** EU import (affects age-reduction eligibility), default true */
  from_eu?: boolean;
  /** Electric range in km — a PHEV needs ≥50 km (+ low CO₂) for the 75% reduction */
  range_km?: number;
  /** false (novo) → no age reduction, default true */
  used?: boolean;
  vehicle_type?: VehicleType;
  /** Diesel particle surcharge (≥0.001 g/km), default true */
  particulas?: boolean;
}

/** ISV (Imposto Sobre Veículos) result — one-off import/registration tax. */
export interface IsvResult {
  isv: number;
  exempt: boolean;
  note: string | null;
  table?: string;
  base?: number;
  rate_pct?: number;
  min_isv_applied?: boolean;
  breakdown?: Record<string, number>;
  age_years?: number;
  age_reduction_pct?: number;
  [k: string]: unknown;
}

/** IUC (Imposto Único de Circulação) result — annual road tax. */
export interface IucResult {
  iuc: number | null;
  exempt?: boolean;
  note: string | null;
  category?: string | null;
  taxa_cilindrada?: number | null;
  taxa_co2?: number;
  coef?: number;
  diesel_adic?: number;
  co2_adic?: number;
  [k: string]: unknown;
}

/** Full API response — the /isv endpoint returns both taxes plus attribution. */
export interface TaxResult {
  isv: IsvResult;
  iuc: IucResult;
  source?: string;
  disclaimer?: string;
  [k: string]: unknown;
}

export interface ClientOptions {
  /** Override the API base (default https://transparent.pt/api/public). */
  baseUrl?: string;
  /** Request timeout in ms (default 8000). */
  timeoutMs?: number;
  /** Custom fetch (e.g. for tests / non-global-fetch runtimes). */
  fetch?: typeof fetch;
}

const DEFAULT_BASE = "https://transparent.pt/api/public";

/**
 * A maintained estimate, cross-checked against the official AT simulator; not the official
 * AT figure. Verbatim honesty note — surfaced for callers that want to show it to users.
 */
export const DISCLAIMER =
  "A maintained estimate, cross-checked against the official AT simulator; not the official AT figure.";

function toQuery(q: TaxQuery): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v !== undefined && v !== null) p.set(k, String(v));
  }
  return p.toString();
}

export class PortugalVehicleTax {
  private baseUrl: string;
  private timeoutMs: number;
  private fetchFn: typeof fetch;

  constructor(opts: ClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE).replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs ?? 8000;
    const f = opts.fetch ?? globalThis.fetch;
    if (!f) {
      throw new Error(
        "No fetch available. Use Node 18+, a browser, or pass { fetch } in ClientOptions."
      );
    }
    this.fetchFn = f;
  }

  /** ISV + IUC for a vehicle (single API call). */
  async getTax(query: TaxQuery): Promise<TaxResult> {
    const url = `${this.baseUrl}/isv?${toQuery(query)}`;
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), this.timeoutMs);
    try {
      const res = await this.fetchFn(url, {
        signal: ctrl.signal,
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        throw new Error(`TransparentCars API ${res.status} ${res.statusText} for ${url}`);
      }
      return (await res.json()) as TaxResult;
    } finally {
      clearTimeout(t);
    }
  }

  /** Convenience: just the ISV part. */
  async getIsv(query: TaxQuery): Promise<IsvResult> {
    return (await this.getTax(query)).isv;
  }

  /** Convenience: just the IUC part. */
  async getIuc(query: TaxQuery): Promise<IucResult> {
    return (await this.getTax(query)).iuc;
  }
}

/** One-shot helper without constructing a client. */
export async function getTax(query: TaxQuery, opts?: ClientOptions): Promise<TaxResult> {
  return new PortugalVehicleTax(opts).getTax(query);
}

export default PortugalVehicleTax;
