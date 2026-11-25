"use client";

import React, { useEffect } from "react";
import { Badge, Card, ErrorState, LoadingIndicator } from "@flatmate/ui";
import { useApiQuery } from "@/hooks/useApiQuery";
import {
  formatMs,
  formatRate,
  formatUptime,
  healthLabel,
  healthTone,
  poolUse,
  trafficHealth,
  type TrafficSnapshot,
} from "@/lib/traffic-model";

const REFRESH_MS = 10_000;

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-charcoal-muted">{label}</p>
      <p className="text-2xl font-bold text-charcoal mt-1" data-testid={`traffic-${label.toLowerCase().replace(/\s+/g, "-")}`}>
        {value}
      </p>
      {hint && <p className="text-xs text-charcoal-muted mt-1">{hint}</p>}
    </Card>
  );
}

/** Live traffic over the last minute, refreshed every 10 seconds (GET /admin/traffic). */
export function TrafficPanel() {
  const query = useApiQuery<TrafficSnapshot>("/admin/traffic");
  const { refetch } = query;

  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refetch();
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [refetch]);

  if (query.error && !query.data) {
    return <ErrorState title="Couldn't load traffic" message={query.error.message} onRetry={refetch} />;
  }
  if (!query.data) return <LoadingIndicator text="Loading traffic…" />;

  const s = query.data;
  const verdict = trafficHealth(s);
  const pool = poolUse(s);
  const refused = s.shed + s.unavailable + s.timeouts;

  return (
    <div className="space-y-4" aria-live="polite">
      <Card className="p-4 flex flex-wrap items-center gap-3">
        <Badge variant={healthTone(verdict.health)} data-testid="traffic-health">{healthLabel(verdict.health)}</Badge>
        <p className="text-sm text-charcoal">{verdict.reasons.join(" · ")}</p>
        <p className="text-xs text-charcoal-muted ml-auto">
          Last {s.window_seconds / 60} minute ·{" "}
          {s.scope === "all_instances"
            ? `${s.instances} instance${s.instances === 1 ? "" : "s"}`
            : "this instance only (Redis isn't connected)"}
          {" "}· updates every {REFRESH_MS / 1000}s
        </p>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile label="Requests" value={formatRate(s.requests_per_second)} hint={`${s.requests.toLocaleString()} in the last minute`} />
        <Tile label="Errors" value={`${(s.error_rate * 100).toFixed(2)}%`} hint={`${s.status["5xx"]} server errors, ${s.status["4xx"]} refused or invalid`} />
        <Tile label="Typical response" value={formatMs(s.latency_ms.p50)} hint={`slowest 5%: ${formatMs(s.latency_ms.p95)}, 1%: ${formatMs(s.latency_ms.p99)}`} />
        <Tile label="Turned away" value={String(refused)} hint={`${s.shed} busy, ${s.unavailable} database busy, ${s.timeouts} timed out`} />
        <Tile label="In progress" value={String(s.in_flight)} hint="requests being handled now" />
        <Tile label="Live connections" value={s.websockets.toLocaleString()} hint="open chat and notification sockets" />
        <Tile
          label="Database connections"
          value={`${s.db_pool.checked_out} / ${s.db_pool.limit || "–"}`}
          hint={pool === null ? "no pool numbers" : `${Math.round(pool * 100)}% in use`}
        />
        <Tile
          label="Instances"
          value={String(s.instances)}
          hint={`serving traffic now · loop delay ${formatMs(s.loop_lag_ms ?? 0)}`}
        />
      </div>

      <Card className="p-4 overflow-x-auto">
        <h3 className="text-sm font-semibold text-charcoal mb-3">Busiest routes</h3>
        {s.routes.length === 0 ? (
          <p className="text-sm text-charcoal-muted">No requests in the last minute.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-charcoal-muted">
                <th className="py-1 pr-4 font-medium">Route</th>
                <th className="py-1 pr-4 font-medium text-right">Requests</th>
                <th className="py-1 pr-4 font-medium text-right">Server errors</th>
                <th className="py-1 font-medium text-right">Slowest 5%</th>
              </tr>
            </thead>
            <tbody>
              {s.routes.map((r) => (
                <tr key={r.route} className="border-t border-gray-100" data-testid="traffic-route">
                  <td className="py-1.5 pr-4 font-mono text-xs break-all">{r.route}</td>
                  <td className="py-1.5 pr-4 text-right">{r.requests.toLocaleString()}</td>
                  <td className={`py-1.5 pr-4 text-right ${r.errors ? "text-red-700 font-semibold" : ""}`}>{r.errors}</td>
                  <td className="py-1.5 text-right">{formatMs(r.p95_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {s.per_instance.length > 1 && (
        <Card className="p-4 overflow-x-auto">
          <h3 className="text-sm font-semibold text-charcoal mb-3">Instances</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-charcoal-muted">
                <th className="py-1 pr-4 font-medium">Instance</th>
                <th className="py-1 pr-4 font-medium text-right">Up</th>
                <th className="py-1 pr-4 font-medium text-right">Requests</th>
                <th className="py-1 pr-4 font-medium text-right">In progress</th>
                <th className="py-1 pr-4 font-medium text-right">Sockets</th>
                <th className="py-1 font-medium text-right">DB connections</th>
              </tr>
            </thead>
            <tbody>
              {s.per_instance.map((i) => (
                <tr key={i.instance ?? "?"} className="border-t border-gray-100">
                  <td className="py-1.5 pr-4 font-mono text-xs break-all">{i.instance}</td>
                  <td className="py-1.5 pr-4 text-right">{formatUptime(i.uptime_seconds)}</td>
                  <td className="py-1.5 pr-4 text-right">{i.requests.toLocaleString()}</td>
                  <td className="py-1.5 pr-4 text-right">{i.in_flight}</td>
                  <td className="py-1.5 pr-4 text-right">{i.websockets}</td>
                  <td className="py-1.5 text-right">{i.db_pool.checked_out ?? "–"} / {i.db_pool.limit ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
