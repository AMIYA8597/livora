"""
Background worker entrypoint for hosts that expect the container to serve HTTP (Cloud Run
services, most PaaS):

    python -m app.workers.run

Starts the Celery worker as a child process, with the beat scheduler embedded unless
WORKER_EMBED_BEAT=false, and serves GET /health on $PORT:

  - 503 until the worker has connected to the broker and is taking tasks (Celery's
    worker_ready signal writes WORKER_READY_FILE), so a deploy whose Redis is unreachable fails
    its startup probe instead of going live doing nothing;
  - 200 while it runs;
  - 503 once it has stopped. This process then exits with Celery's exit code, so the host
    restarts the container.

Exactly one beat may run, or every scheduled task runs once per beat: run this as a single
instance (Cloud Run: --min-instances=1 --max-instances=1). The scheduled jobs tolerate the brief
overlap of a rolling deploy (the outbox and account purge claim rows with SKIP LOCKED).

SIGTERM is passed to Celery, which finishes its current tasks (warm shutdown); tasks are acked
late, so one cut off by the host's kill is delivered again.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, List, Mapping, Optional

# The worker runs alone in its own container, so its /tmp is private to it.
DEFAULT_READY_FILE = "/tmp/flatmate-worker-ready"  # nosec B108
DEFAULT_SCHEDULE_FILE = "/tmp/celerybeat-schedule"  # nosec B108


def _flag(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def celery_command(env: Mapping[str, str]) -> List[str]:
    """The Celery worker command line for this environment."""
    cmd = [
        sys.executable, "-m", "celery", "-A", "app.workers.celery_app", "worker",
        f"--loglevel={env.get('WORKER_LOG_LEVEL', 'info')}",
        f"--concurrency={int(env.get('WORKER_CONCURRENCY', '2'))}",
        # One beat per deployment, and nothing to gain from gossip between workers.
        "--without-gossip", "--without-mingle",
    ]
    if env.get("WORKER_POOL"):  # e.g. "solo" on Windows, where the default prefork pool can't run
        cmd.append(f"--pool={env['WORKER_POOL']}")
    if _flag(env.get("WORKER_EMBED_BEAT"), True):
        cmd += ["--beat", f"--schedule={env.get('CELERY_BEAT_SCHEDULE_FILE', DEFAULT_SCHEDULE_FILE)}"]
    return cmd


def health_status(process: Optional[subprocess.Popen], ready_file: str) -> int:
    """HTTP status for /health: 200 only while Celery runs and has reported ready."""
    if process is None or process.poll() is not None:
        return 503
    return 200 if os.path.exists(ready_file) else 503


def make_handler(status: Callable[[], int]) -> type:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            code = status() if self.path.split("?")[0] in ("/", "/health") else 404
            body = {200: b"ok\n", 404: b"not found\n"}.get(code, b"not ready\n")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # probes every few seconds
            return

    return HealthHandler


def main() -> int:
    env = dict(os.environ)
    ready_file = env.setdefault("WORKER_READY_FILE", DEFAULT_READY_FILE)
    try:
        os.remove(ready_file)  # a stale file from a previous run must not report ready
    except FileNotFoundError:
        pass

    process = subprocess.Popen(celery_command(env), env=env)

    # Cloud Run sends health checks to $PORT on the container's own interface.
    host = "0.0.0.0"  # nosec B104
    server = ThreadingHTTPServer(
        (host, int(env.get("PORT", "8080"))),
        make_handler(lambda: health_status(process, ready_file)),
    )
    threading.Thread(target=server.serve_forever, name="health", daemon=True).start()

    def stop(signum: int, _frame: object) -> None:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    code = process.wait()
    server.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
