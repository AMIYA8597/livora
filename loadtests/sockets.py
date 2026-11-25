"""
Realtime load: hold N signed-in sockets the way browser tabs do (auth frame, a ping every 25 s)
and report how many connected, how long the handshake took, and how many dropped.

    python loadtests/sockets.py --url ws://localhost:8000/api/v1/messaging/ws --sockets 2000 \
        --ramp 100 --hold 300

Tokens come from loadtests/.tokens.json (seed_load.py), one member per socket (a member may hold
up to 10). Exits 1 if fewer than --min-connected (default 99%) connected or more than 1% dropped.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import websockets

TOKENS = Path(__file__).with_name(".tokens.json")
PING_SECONDS = 25


class Tally:
    def __init__(self) -> None:
        self.connected = 0
        self.failed = 0
        self.dropped = 0
        self.handshake_ms: list[float] = []
        self.pong_ms: list[float] = []
        self.errors: dict[str, int] = {}

    def error(self, kind: str) -> None:
        self.errors[kind] = self.errors.get(kind, 0) + 1


async def hold(url: str, token: str, until: float, tally: Tally) -> None:
    start = time.perf_counter()
    ready_seen = False
    try:
        async with websockets.connect(url, open_timeout=20, ping_interval=None, max_size=2**20) as ws:
            await ws.send(json.dumps({"event": "auth", "data": {"token": token}}))
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if ready.get("event") != "connection.ready":
                tally.failed += 1
                tally.error(f"not ready: {ready.get('event')}")
                return
            tally.connected += 1
            ready_seen = True
            tally.handshake_ms.append((time.perf_counter() - start) * 1000)
            while time.time() < until:
                await asyncio.sleep(min(PING_SECONDS, max(0.0, until - time.time())))
                if time.time() >= until:
                    break
                sent = time.perf_counter()
                await ws.send(json.dumps({"event": "ping", "data": {}}))
                while True:  # skip presence and other events until our pong
                    frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                    if frame.get("event") == "pong":
                        tally.pong_ms.append((time.perf_counter() - sent) * 1000)
                        break
    except Exception as exc:  # noqa: BLE001 - every failure is counted, not raised
        # Lost after it was up: dropped. Never got up: failed.
        if ready_seen:
            tally.dropped += 1
        else:
            tally.failed += 1
        tally.error(type(exc).__name__)


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--sockets", type=int, default=1000)
    p.add_argument("--ramp", type=float, default=100, help="new sockets per second")
    p.add_argument("--hold", type=float, default=120, help="seconds to keep them open after the ramp")
    p.add_argument("--min-connected", type=float, default=0.99)
    args = p.parse_args()

    members = json.loads(TOKENS.read_text(encoding="utf-8"))["members"]
    tally = Tally()
    ramp_seconds = args.sockets / args.ramp
    until = time.time() + ramp_seconds + args.hold
    tasks = []
    for i in range(args.sockets):
        tasks.append(asyncio.create_task(hold(args.url, members[i % len(members)]["token"], until, tally)))
        await asyncio.sleep(1 / args.ramp)
        if i and i % 500 == 0:
            print(f"opened {i}, connected {tally.connected}, failed {tally.failed}")
    await asyncio.gather(*tasks)

    share = tally.connected / args.sockets
    print(json.dumps({
        "sockets": args.sockets, "connected": tally.connected, "failed": tally.failed, "dropped": tally.dropped,
        "handshake_ms": {"p50": round(statistics.median(tally.handshake_ms), 1) if tally.handshake_ms else None,
                         "p95": round(pct(tally.handshake_ms, 0.95), 1)},
        "pong_ms": {"p50": round(statistics.median(tally.pong_ms), 1) if tally.pong_ms else None,
                    "p95": round(pct(tally.pong_ms, 0.95), 1)},
        "errors": tally.errors,
    }, indent=2))
    ok = share >= args.min_connected and tally.dropped <= 0.01 * args.sockets
    print("SOCKETS PASSED" if ok else "SOCKETS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
