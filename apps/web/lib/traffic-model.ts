/**
 * The admin Traffic tab's rules: what GET /admin/traffic returns and how healthy it looks.
 * Pure, so they're tested without a browser (tests/traffic_model.test.ts). The thresholds match
 * the alert policies in infrastructure/monitoring/ and docs/CAPACITY_PLAN.md.
 */

export interface TrafficRoute {
  route: string;
  requests: number;
  errors: number;
  p95_ms: number | null;
}

export interface TrafficInstance {
  instance: string | null;
  uptime_seconds: number | null;
  requests: number;
  in_flight: number;
  websockets: number;
  loop_lag_ms?: number;
  db_pool: { checked_out?: number; idle?: number; limit?: number };
}

export interface TrafficSnapshot {
  scope: "all_instances" | "this_instance";
  window_seconds: number;
  instances: number;
  requests: number;
  requests_per_second: number;
  status: { "2xx": number; "3xx": number; "4xx": number; "5xx": number };
  error_rate: number;
  latency_ms: { p50: number | null; p95: number | null; p99: number | null };
  shed: number;
  timeouts: number;
  unavailable: number;
  in_flight: number;
  websockets: number;
  /** Worst event-loop delay across instances: CPU saturation or a blocking call. */
  loop_lag_ms?: number;
  db_pool: { checked_out: number; limit: number };
  routes: TrafficRoute[];
  per_instance: TrafficInstance[];
}

export type TrafficHealth = "idle" | "healthy" | "strained" | "failing";

/** Thresholds. Strained: users may notice. Failing: users are getting errors. */
export const LIMITS = {
  errorRateStrained: 0.01,
  errorRateFailing: 0.05,
  p95StrainedMs: 1000,
  p95FailingMs: 3000,
  poolStrained: 0.8,
  refusedFailing: 0.02,
  loopLagStrainedMs: 200,
} as const;

export interface HealthVerdict {
  health: TrafficHealth;
  reasons: string[];
}

export function poolUse(snapshot: Pick<TrafficSnapshot, "db_pool">): number | null {
  const { checked_out, limit } = snapshot.db_pool;
  return limit > 0 ? checked_out / limit : null;
}

/** How the last minute looks, with the reasons in plain words. */
export function trafficHealth(s: TrafficSnapshot): HealthVerdict {
  if (s.requests === 0) return { health: "idle", reasons: ["No requests in the last minute."] };
  const failing: string[] = [];
  const strained: string[] = [];
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

  if (s.error_rate >= LIMITS.errorRateFailing) failing.push(`${pct(s.error_rate)} of requests failed`);
  else if (s.error_rate >= LIMITS.errorRateStrained) strained.push(`${pct(s.error_rate)} of requests failed`);

  const p95 = s.latency_ms.p95;
  if (p95 !== null && p95 >= LIMITS.p95FailingMs) failing.push(`slowest 5% take ${formatMs(p95)}`);
  else if (p95 !== null && p95 >= LIMITS.p95StrainedMs) strained.push(`slowest 5% take ${formatMs(p95)}`);

  const refused = s.shed + s.unavailable + s.timeouts;
  if (refused > 0) {
    const share = refused / s.requests;
    const words = `${refused} request${refused === 1 ? "" : "s"} turned away (busy or timed out)`;
    (share >= LIMITS.refusedFailing ? failing : strained).push(words);
  }

  const pool = poolUse(s);
  if (pool !== null && pool >= LIMITS.poolStrained) strained.push(`database connections ${pct(pool)} in use`);

  const lag = s.loop_lag_ms ?? 0;
  if (lag >= LIMITS.loopLagStrainedMs) strained.push(`servers are CPU-bound (${formatMs(lag)} behind)`);

  if (failing.length) return { health: "failing", reasons: [...failing, ...strained] };
  if (strained.length) return { health: "strained", reasons: strained };
  return { health: "healthy", reasons: ["Everything is within limits."] };
}

export function healthLabel(h: TrafficHealth): string {
  return { idle: "Idle", healthy: "Healthy", strained: "Under strain", failing: "Failing" }[h];
}

export function healthTone(h: TrafficHealth): "default" | "success" | "warning" | "danger" {
  return ({ idle: "default", healthy: "success", strained: "warning", failing: "danger" } as const)[h];
}

export function formatMs(ms: number | null): string {
  if (ms === null) return "–";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

export function formatRate(perSecond: number): string {
  return perSecond >= 10 ? `${Math.round(perSecond)}/s` : `${perSecond.toFixed(1)}/s`;
}

export function formatUptime(seconds: number | null): string {
  if (seconds === null) return "–";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}
