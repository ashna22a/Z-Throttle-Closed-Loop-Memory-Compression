"""Reads real-time memory and CPU metrics from procfs."""

import os
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemVitals:
    mem_used_pct: float
    cpu_load_pct: float      # per-core normalized 0.0 - 1.0+
    mem_total_mb: float
    mem_available_mb: float
    load_avg_1m: float
    cpu_cores: int
    timestamp: float


class SystemMonitor:
    """Polls /proc/meminfo and /proc/loadavg."""

    def __init__(self, meminfo_path: str, loadavg_path: str):
        self.meminfo_path = meminfo_path
        self.loadavg_path = loadavg_path
        self.cpu_cores = os.cpu_count() or 1

    def _read_meminfo(self) -> dict:
        info = {}
        with open(self.meminfo_path, "r") as f:
            for line in f:
                key, _, rest = line.partition(":")
                value = rest.strip().split()[0]  # kB
                info[key.strip()] = int(value)
        return info

    def _read_loadavg(self) -> float:
        with open(self.loadavg_path, "r") as f:
            return float(f.read().split()[0])

    def sample(self) -> SystemVitals:
        mi = self._read_meminfo()
        total_kb = mi.get("MemTotal", 1)
        avail_kb = mi.get("MemAvailable", mi.get("MemFree", 0))
        used_kb = total_kb - avail_kb

        mem_used_pct = (used_kb / total_kb) * 100.0
        load_1m = self._read_loadavg()
        cpu_load_pct = load_1m / self.cpu_cores  # 1.0 == fully busy

        return SystemVitals(
            mem_used_pct=mem_used_pct,
            cpu_load_pct=cpu_load_pct,
            mem_total_mb=total_kb / 1024.0,
            mem_available_mb=avail_kb / 1024.0,
            load_avg_1m=load_1m,
            cpu_cores=self.cpu_cores,
            timestamp=time.time(),
        )
