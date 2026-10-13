"""Tunable configuration for the Z-Throttle governor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Loop timing
    poll_interval_sec: float = 1.5

    # Memory thresholds (percent of RAM used)
    mem_high_watermark: float = 75.0      # start compressing aggressively
    mem_critical_watermark: float = 85.0  # emergency boost
    mem_low_watermark: float = 60.0       # hysteresis: relax

    # CPU thresholds (load average normalized by core count)
    cpu_high_watermark: float = 0.80      # 80% per-core utilization
    cpu_low_watermark: float = 0.50       # hysteresis: back to normal

    # Swappiness targets
    swappiness_idle: int = 60             # baseline
    swappiness_aggressive: int = 160      # memory-critical, CPU relaxed
    swappiness_emergency: int = 180       # memory-critical + CPU idle
    swappiness_defensive: int = 20        # compute-critical

    # Smoothing / control-loop stability
    ema_alpha: float = 0.35               # exponential moving average weight
    min_dwell_sec: float = 3.0            # min time before changing state

    # Paths (Linux procfs/sysfs)
    meminfo_path: str = "/proc/meminfo"
    loadavg_path: str = "/proc/loadavg"
    swappiness_path: str = "/proc/sys/vm/swappiness"
    log_path: str = "/var/log/z-throttle.log"

    # Set True to print decisions without touching the kernel
    dry_run: bool = False
