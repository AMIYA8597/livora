"""
The deployable worker process (app.workers.run): its Celery command line, the health check the
host probes, and TLS for managed Redis.
"""
import os
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.workers.celery_app import redis_tls_options
from app.workers.run import celery_command, health_status

API_ROOT = Path(__file__).resolve().parents[1]


def test_beat_is_embedded_by_default_with_a_writable_schedule():
    cmd = celery_command({})
    assert cmd[1:6] == ["-m", "celery", "-A", "app.workers.celery_app", "worker"]
    assert "--beat" in cmd
    assert "--schedule=/tmp/celerybeat-schedule" in cmd
    assert "--concurrency=2" in cmd
    assert not any(c.startswith("--pool") for c in cmd)


def test_beat_can_be_turned_off_and_pool_and_concurrency_set():
    cmd = celery_command({"WORKER_EMBED_BEAT": "false", "WORKER_CONCURRENCY": "4", "WORKER_POOL": "solo"})
    assert "--beat" not in cmd
    assert "--concurrency=4" in cmd
    assert "--pool=solo" in cmd


class _Proc:
    def __init__(self, code):
        self._code = code

    def poll(self):
        return self._code


def test_health_is_ready_only_while_running_after_the_ready_signal(tmp_path):
    ready = tmp_path / "ready"
    assert health_status(None, str(ready)) == 503
    assert health_status(_Proc(None), str(ready)) == 503  # started, not yet consuming
    ready.write_text("ready")
    assert health_status(_Proc(None), str(ready)) == 200
    assert health_status(_Proc(1), str(ready)) == 503  # Celery has exited


def test_rediss_urls_verify_certificates_unless_told_otherwise():
    assert redis_tls_options("rediss://default:pw@example.upstash.io:6379") == {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    assert redis_tls_options("rediss://host:6379/0?ssl_cert_reqs=CERT_NONE") is None
    assert redis_tls_options("redis://localhost:6379/1") is None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _health(port: int) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as res:
            return res.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def test_entrypoint_reports_ready_once_celery_consumes_and_stops_cleanly(tmp_path):
    port = _free_port()
    env = {
        **os.environ,
        "PORT": str(port),
        # An in-process broker: the test needs Celery to start, not Redis.
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "WORKER_READY_FILE": str(tmp_path / "ready"),
        "WORKER_POOL": "solo",
        "WORKER_CONCURRENCY": "1",
        # Celery can't embed beat on Windows; the command line with beat is covered above.
        "WORKER_EMBED_BEAT": "false" if sys.platform == "win32" else "true",
        "CELERY_BEAT_SCHEDULE_FILE": str(tmp_path / "beat-schedule"),
    }
    proc = subprocess.Popen([sys.executable, "-m", "app.workers.run"], cwd=API_ROOT, env=env)
    try:
        seen = set()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            code = _health(port)
            seen.add(code)
            if code == 200:
                break
            assert proc.poll() is None, "the worker exited before becoming ready"
            time.sleep(0.5)
        assert 200 in seen, f"never ready; saw {seen}"

        if sys.platform != "win32":
            proc.send_signal(signal.SIGTERM)
            assert proc.wait(timeout=30) == 0
            assert not (tmp_path / "ready").exists()
    finally:
        if proc.poll() is None:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            else:
                proc.kill()
            proc.wait(timeout=10)
