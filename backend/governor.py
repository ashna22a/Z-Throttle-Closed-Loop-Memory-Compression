"""Closed-loop decision engine: maps (mem, cpu) -> swappiness."""

import time
from enum import Enum
from typing import Optional

from config import Config
from monitor import SystemVitals


class State(str, Enum):
    NORMAL = "NORMAL"
    MEMORY_PRESSURE = "MEMORY_PRESSURE"      # tight RAM + relaxed CPU
    EMERGENCY = "EMERGENCY"                  # critical RAM + idle CPU
    COMPUTE_CRITICAL = "COMPUTE_CRITICAL"    # CPU slammed


class Governor:
    """
    State machine with hysteresis + EMA smoothing.

    Hysteresis prevents flapping between states when metrics hover
    near a threshold. EMA smoothing prevents single noisy samples
    from triggering a state change.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._state: State = State.NORMAL
        self._last_change_ts: float = 0.0
        self._ema_mem: Optional[float] = None
        self._ema_cpu: Optional[float] = None

    # ---- helpers -------------------------------------------------------

    def _smooth(self, prev: Optional[float], new: float) -> float:
        a = self.cfg.ema_alpha
        return new if prev is None else (a * new + (1 - a) * prev)

    def _dwell_ok(self, now: float) -> bool:
        return (now - self._last_change_ts) >= self.cfg.min_dwell_sec

    # ---- main entry ----------------------------------------------------

    def decide(self, v: SystemVitals) -> tuple[State, int]:
        """Return (new_state, target_swappiness)."""
        now = v.timestamp
        self._ema_mem = self._smooth(self._ema_mem, v.mem_used_pct)
        self._ema_cpu = self._smooth(self._ema_cpu, v.cpu_load_pct)

        mem = self._ema_mem
        cpu = self._ema_cpu
        c = self.cfg

        # --- Priority 1: protect CPU when compute-bound ----------------
        # Only enter COMPUTE_CRITICAL if we aren't in EMERGENCY (OOM risk
        # trumps latency; freezing is worse than slow threads).
        if cpu >= c.cpu_high_watermark and self._state != State.EMERGENCY:
            new_state = State.COMPUTE_CRITICAL

        # --- Priority 2: memory pressure -------------------------------
        elif mem >= c.mem_critical_watermark and cpu < c.cpu_high_watermark:
            new_state = State.EMERGENCY

        elif mem >= c.mem_high_watermark and cpu < c.cpu_low_watermark:
            new_state = State.MEMORY_PRESSURE

        # --- Hysteresis: exit conditions require relaxed metrics -------
        elif self._state == State.COMPUTE_CRITICAL and cpu < c.cpu_low_watermark:
            new_state = State.NORMAL

        elif self._state in (State.MEMORY_PRESSURE, State.EMERGENCY) \
                and mem < c.mem_low_watermark:
            new_state = State.NORMAL

        elif self._state == State.EMERGENCY and mem < c.mem_critical_watermark \
                and cpu < c.cpu_high_watermark:
            new_state = State.MEMORY_PRESSURE

        else:
            new_state = self._state  # hold current state

        # --- Dwell time enforcement ------------------------------------
        if new_state != self._state and self._dwell_ok(now):
            self._state = new_state
            self._last_change_ts = now
        elif new_state != self._state:
            # Want to transition but not enough dwell time yet
            new_state = self._state

        return self._state, self._swappiness_for(self._state)

    def _swappiness_for(self, state: State) -> int:
        c = self.cfg
        return {
            State.NORMAL:            c.swappiness_idle,
            State.MEMORY_PRESSURE:   c.swappiness_aggressive,
            State.EMERGENCY:         c.swappiness_emergency,
            State.COMPUTE_CRITICAL:  c.swappiness_defensive,
        }[state]
