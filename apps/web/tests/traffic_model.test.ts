import test from 'node:test';
import assert from 'node:assert';
import { formatMs, formatRate, formatUptime, poolUse, trafficHealth, type TrafficSnapshot } from '../lib/traffic-model.ts';

function snap(over: Partial<TrafficSnapshot> = {}): TrafficSnapshot {
  return {
    scope: 'all_instances', window_seconds: 60, instances: 2, requests: 6000, requests_per_second: 100,
    status: { '2xx': 5900, '3xx': 0, '4xx': 100, '5xx': 0 }, error_rate: 0,
    latency_ms: { p50: 20, p95: 180, p99: 400 }, shed: 0, timeouts: 0, unavailable: 0, in_flight: 12,
    websockets: 900, db_pool: { checked_out: 8, limit: 60 }, routes: [], per_instance: [], ...over,
  };
}

test('a normal minute is healthy', () => {
  assert.deepStrictEqual(trafficHealth(snap()), { health: 'healthy', reasons: ['Everything is within limits.'] });
});

test('no traffic is idle, not healthy or failing', () => {
  assert.strictEqual(trafficHealth(snap({ requests: 0 })).health, 'idle');
});

test('errors, slowness, refusals and a full pool are explained', () => {
  const strained = trafficHealth(snap({ error_rate: 0.02, latency_ms: { p50: 300, p95: 1500, p99: 2500 }, db_pool: { checked_out: 50, limit: 60 } }));
  assert.strictEqual(strained.health, 'strained');
  assert.deepStrictEqual(strained.reasons, ['2.0% of requests failed', 'slowest 5% take 1.5 s', 'database connections 83.3% in use']);

  const failing = trafficHealth(snap({ error_rate: 0.08 }));
  assert.strictEqual(failing.health, 'failing');

  const slow = trafficHealth(snap({ latency_ms: { p50: 900, p95: 4000, p99: 9000 } }));
  assert.strictEqual(slow.health, 'failing');

  // A few refusals are strain; many (2%+) mean users are being turned away.
  assert.strictEqual(trafficHealth(snap({ shed: 1 })).health, 'strained');
  assert.deepStrictEqual(trafficHealth(snap({ shed: 1 })).reasons, ['1 request turned away (busy or timed out)']);
  const turnedAway = trafficHealth(snap({ shed: 100, unavailable: 20, timeouts: 10 }));
  assert.strictEqual(turnedAway.health, 'failing');
  assert.deepStrictEqual(turnedAway.reasons, ['130 requests turned away (busy or timed out)']);
});

test('pool use is a share, or unknown without a limit', () => {
  assert.strictEqual(poolUse(snap({ db_pool: { checked_out: 15, limit: 60 } })), 0.25);
  assert.strictEqual(poolUse(snap({ db_pool: { checked_out: 0, limit: 0 } })), null);
});

test('numbers read naturally', () => {
  assert.strictEqual(formatMs(null), '–');
  assert.strictEqual(formatMs(12.4), '12 ms');
  assert.strictEqual(formatMs(1530), '1.5 s');
  assert.strictEqual(formatRate(2.345), '2.3/s');
  assert.strictEqual(formatRate(1234.5), '1235/s');
  assert.strictEqual(formatUptime(42), '42s');
  assert.strictEqual(formatUptime(600), '10m');
  assert.strictEqual(formatUptime(3 * 3600 + 120), '3h 2m');
  assert.strictEqual(formatUptime(2 * 86400 + 3600), '2d 1h');
});

test('a CPU-bound server shows as strain', () => {
  const v = trafficHealth(snap({ loop_lag_ms: 350 }));
  assert.strictEqual(v.health, 'strained');
  assert.deepStrictEqual(v.reasons, ['servers are CPU-bound (350 ms behind)']);
  assert.strictEqual(trafficHealth(snap({ loop_lag_ms: 20 })).health, 'healthy');
});
