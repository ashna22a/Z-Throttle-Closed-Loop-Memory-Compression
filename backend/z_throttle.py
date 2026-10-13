#!/usr/bin/env python3
"""
Z-Throttle: Closed-Loop Memory Compression Governor
and Dynamic Swappiness Arbiter.

Usage:
    sudo python3 z_throttle.py
    sudo python3 z_throttle.py --dry-run
    sudo python3 z_throttle.py --interval 1.0
"""

import argparse
import signal
import sys
import time

from arbiter import SwappinessArbiter
from config import Config
from governor import Governor, State
from logger import get_logger
from monitor import SystemMonitor


_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    _shutdown = True


def run(cfg: Config) -> None:
    log = get_logger("z_throttle", cfg.log_path)

    log.info("=" * 60)
    log.info("Z-Throttle governor starting")
    log.info("  poll=%.2fs  mem_hi=%.0f%%  cpu_hi=%.0f%%  dry_run=%s",
             cfg.poll_interval_sec, cfg.mem_high_watermark,
             cfg.cpu_high_watermark * 100, cfg.dry_run)
    log.info("=" * 60)

    monitor = SystemMonitor(cfg.meminfo_path, cfg.loadavg_path)
    governor = Governor(cfg)
    arbiter = SwappinessArbiter(cfg)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    last_state = None

    while not _shutdown:
        try:
            vitals = monitor.sample()
            state, target = governor.decide(vitals)

            # Log on state change OR any time we're not NORMAL
            if state != last_state:
                log.info(
                    "STATE -> %s | mem=%.1f%% cpu=%.0f%% load1=%.2f "
                    "target_swappiness=%d avail=%.0fMB",
                    state.value, vitals.mem_used_pct,
                    vitals.cpu_load_pct * 100, vitals.load_avg_1m,
                    target, vitals.mem_available_mb,
                )
                last_state = state
            else:
                log.debug(
                    "hold %s | mem=%.1f%% cpu=%.0f%% swappiness=%d",
                    state.value, vitals.mem_used_pct,
                    vitals.cpu_load_pct * 100, target,
                )

            arbiter.apply(target)

        except FileNotFoundError as e:
            log.error("procfs file missing: %s (are you on Linux?)", e)
            time.sleep(cfg.poll_interval_sec)
        except Exception as e:
            log.exception("Unexpected error in loop: %s", e)
            time.sleep(cfg.poll_interval_sec)
            continue

        # Sleep in small slices so SIGTERM is responsive
        deadline = time.time() + cfg.poll_interval_sec
        while not _shutdown and time.time() < deadline:
            time.sleep(0.1)

    log.info("Z-Throttle shutting down cleanly.")


def parse_args() -> Config:
    p = argparse.ArgumentParser(description="Z-Throttle governor")
    p.add_argument("--dry-run", action="store_true",
                   help="Log decisions without modifying the kernel")
    p.add_argument("--interval", type=float, default=None,
                   help="Poll interval seconds (default 1.5)")
    p.add_argument("--mem-high", type=float, default=None,
                   help="Memory high watermark percent")
    p.add_argument("--cpu-high", type=float, default=None,
                   help="CPU high watermark (fraction of cores, 0-1)")
    args = p.parse_args()

    cfg = Config()
    overrides = {}
    if args.interval is not None:
        overrides["poll_interval_sec"] = args.interval
    if args.mem_high is not None:
        overrides["mem_high_watermark"] = args.mem_high
    if args.cpu_high is not None:
        overrides["cpu_high_watermark"] = args.cpu_high
    if args.dry_run:
        overrides["dry_run"] = True

    return Config(**{**cfg.__dict__, **overrides}) if overrides else cfg


if __name__ == "__main__":
    if sys.platform != "linux":
        print("Z-Throttle requires Linux (procfs).", file=sys.stderr)
        sys.exit(1)
    run(parse_args())
