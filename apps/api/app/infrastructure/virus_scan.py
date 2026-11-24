"""
Virus scanning for uploads through a ClamAV daemon (clamd) over TCP.

Set CLAMAV_HOST (and CLAMAV_PORT if it isn't 3310) to turn scanning on. Files are streamed with
clamd's INSTREAM command, so nothing is written to disk on either side. With
VIRUS_SCAN_REQUIRED=true an upload is refused when the scanner is missing or unreachable;
otherwise it is accepted and the outage is logged.
"""
from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import Literal, Optional

from app.core.config import settings

logger = logging.getLogger("flatmate.storage")

CHUNK = 64 * 1024
Verdict = Literal["clean", "infected", "unavailable", "disabled"]


@dataclass(frozen=True)
class ScanResult:
    verdict: Verdict
    signature: Optional[str] = None


def scanning_configured() -> bool:
    return bool(settings.CLAMAV_HOST)


async def scan_bytes(data: bytes) -> ScanResult:
    if not scanning_configured():
        return ScanResult("disabled")
    try:
        return await asyncio.wait_for(_instream(data), timeout=settings.CLAMAV_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - any failure to get a verdict is "unavailable"
        logger.warning("Virus scanner unavailable: %s", type(exc).__name__)
        return ScanResult("unavailable")


async def _instream(data: bytes) -> ScanResult:
    reader, writer = await asyncio.open_connection(settings.CLAMAV_HOST, settings.CLAMAV_PORT)
    try:
        writer.write(b"zINSTREAM\0")
        for start in range(0, len(data), CHUNK):
            chunk = data[start:start + CHUNK]
            writer.write(struct.pack("!L", len(chunk)) + chunk)
            await writer.drain()
        writer.write(struct.pack("!L", 0))
        await writer.drain()
        reply = (await reader.read(4096)).rstrip(b"\0").decode("utf-8", "replace").strip()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass

    # Replies: "stream: OK", "stream: <Signature> FOUND", "INSTREAM size limit exceeded. ERROR"
    if reply.endswith("OK"):
        return ScanResult("clean")
    if reply.endswith("FOUND"):
        signature = reply.split(":", 1)[-1].strip()[: -len("FOUND")].strip()
        return ScanResult("infected", signature or None)
    raise RuntimeError("Unexpected clamd reply")
