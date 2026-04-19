"""System monitor / supervisor.

Runs a target command as a subprocess, watches it, and restarts it if it
exits unexpectedly. Supports exponential backoff, max-restart cap, optional
HTTP health checks, and graceful shutdown on Ctrl-C.

Usage:
    python system_monitor.py -- python -m prompt_validator --file prompts/good_example.txt
    python system_monitor.py --health-url http://localhost:8000/health -- ./server
    python system_monitor.py --max-restarts 5 --backoff 2 -- npm start
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, msg: str) -> None:
    color = {"INFO": CYAN, "WARN": YELLOW, "ERR": RED, "OK": GREEN}.get(level, "")
    print(f"{DIM}{ts()}{RESET} {color}{BOLD}[{level}]{RESET} {msg}", flush=True)


@dataclass
class SupervisorConfig:
    cmd: list[str]
    max_restarts: int = 0  # 0 = unlimited
    backoff_base: float = 1.0
    backoff_cap: float = 60.0
    health_url: str | None = None
    health_interval: float = 10.0
    health_timeout: float = 5.0
    health_failures_to_restart: int = 3
    cwd: str | None = None


@dataclass
class SupervisorState:
    restarts: int = 0
    backoff: float = 0.0
    stopping: bool = False
    health_failures: int = 0
    proc: subprocess.Popen | None = field(default=None, repr=False)


class Supervisor:
    def __init__(self, cfg: SupervisorConfig) -> None:
        self.cfg = cfg
        self.state = SupervisorState()
        self._health_thread: threading.Thread | None = None

    def _spawn(self) -> subprocess.Popen:
        log("INFO", f"starting: {' '.join(self.cfg.cmd)}")
        return subprocess.Popen(
            self.cfg.cmd,
            cwd=self.cfg.cwd,
            stdout=None,
            stderr=None,
            start_new_session=True,
        )

    def _stop_proc(self, sig: int = signal.SIGTERM, grace: float = 5.0) -> None:
        proc = self.state.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            log("WARN", "process did not exit; sending SIGKILL")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def _next_backoff(self) -> float:
        if self.state.backoff == 0:
            self.state.backoff = self.cfg.backoff_base
        else:
            self.state.backoff = min(self.state.backoff * 2, self.cfg.backoff_cap)
        return self.state.backoff

    def _reset_backoff(self) -> None:
        self.state.backoff = 0.0

    def _health_loop(self) -> None:
        assert self.cfg.health_url is not None
        while not self.state.stopping:
            time.sleep(self.cfg.health_interval)
            if self.state.stopping or self.state.proc is None:
                continue
            if self.state.proc.poll() is not None:
                continue
            try:
                req = urllib.request.Request(self.cfg.health_url)
                with urllib.request.urlopen(req, timeout=self.cfg.health_timeout) as r:
                    ok = 200 <= r.status < 400
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                ok = False
                log("WARN", f"health check failed: {e}")
            if ok:
                if self.state.health_failures:
                    log("OK", "health restored")
                self.state.health_failures = 0
            else:
                self.state.health_failures += 1
                log("WARN",
                    f"health failure {self.state.health_failures}/"
                    f"{self.cfg.health_failures_to_restart}")
                if self.state.health_failures >= self.cfg.health_failures_to_restart:
                    log("ERR", "health threshold exceeded; restarting child")
                    self.state.health_failures = 0
                    self._stop_proc()

    def _install_signal_handlers(self) -> None:
        def handler(sig, _frame):
            log("INFO", f"received signal {sig}; shutting down")
            self.state.stopping = True
            self._stop_proc()
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def run(self) -> int:
        self._install_signal_handlers()

        if self.cfg.health_url:
            self._health_thread = threading.Thread(target=self._health_loop, daemon=True)
            self._health_thread.start()
            log("INFO", f"health checks: {self.cfg.health_url} every {self.cfg.health_interval}s")

        last_exit = 0
        while not self.state.stopping:
            started_at = time.monotonic()
            try:
                self.state.proc = self._spawn()
            except FileNotFoundError as e:
                log("ERR", f"failed to spawn: {e}")
                return 127
            rc = self.state.proc.wait()
            ran_for = time.monotonic() - started_at
            last_exit = rc

            if self.state.stopping:
                log("INFO", f"child exited rc={rc}; supervisor stopping")
                break

            level = "OK" if rc == 0 else "WARN"
            log(level, f"child exited rc={rc} after {ran_for:.1f}s")

            if ran_for > 30:
                self._reset_backoff()

            self.state.restarts += 1
            if self.cfg.max_restarts and self.state.restarts > self.cfg.max_restarts:
                log("ERR", f"max restarts ({self.cfg.max_restarts}) exceeded; giving up")
                return rc if rc != 0 else 1

            delay = self._next_backoff()
            log("INFO",
                f"restart #{self.state.restarts} in {delay:.1f}s "
                f"(backoff cap {self.cfg.backoff_cap:.0f}s)")
            slept = 0.0
            while slept < delay and not self.state.stopping:
                time.sleep(0.1)
                slept += 0.1

        return last_exit


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    p = argparse.ArgumentParser(
        description="Process supervisor: runs a command and restarts it on exit.",
        usage="%(prog)s [options] -- CMD [ARGS...]",
    )
    p.add_argument("--max-restarts", type=int, default=0,
                   help="Cap on restarts (0 = unlimited)")
    p.add_argument("--backoff", type=float, default=1.0,
                   help="Initial backoff seconds (default: 1.0)")
    p.add_argument("--backoff-cap", type=float, default=60.0,
                   help="Maximum backoff seconds (default: 60)")
    p.add_argument("--cwd", default=None, help="Working directory for child")
    p.add_argument("--health-url", default=None,
                   help="Optional HTTP URL to poll; restart child after N failures")
    p.add_argument("--health-interval", type=float, default=10.0,
                   help="Seconds between health checks (default: 10)")
    p.add_argument("--health-timeout", type=float, default=5.0,
                   help="Health check timeout in seconds (default: 5)")
    p.add_argument("--health-fails", type=int, default=3,
                   help="Consecutive health failures before restart (default: 3)")
    args, rest = p.parse_known_args(argv)
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        p.error("missing command after `--`")
    return args, rest


def main(argv: list[str] | None = None) -> int:
    args, cmd = parse_args(argv)
    cfg = SupervisorConfig(
        cmd=cmd,
        max_restarts=args.max_restarts,
        backoff_base=args.backoff,
        backoff_cap=args.backoff_cap,
        health_url=args.health_url,
        health_interval=args.health_interval,
        health_timeout=args.health_timeout,
        health_failures_to_restart=args.health_fails,
        cwd=args.cwd,
    )
    return Supervisor(cfg).run()


if __name__ == "__main__":
    sys.exit(main())
