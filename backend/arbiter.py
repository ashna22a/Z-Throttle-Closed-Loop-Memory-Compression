"""Applies the governor's decision to the kernel."""

from typing import Optional
from config import Config
from logger import get_logger

log = get_logger(__name__)


class SwappinessArbiter:
    """Writes swappiness to /proc/sys/vm/swappiness (or dry-runs)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._last_written: Optional[int] = None
        if not cfg.dry_run:
            self._validate()

    def _validate(self) -> None:
        # Read current value to confirm we have permission
        try:
            with open(self.cfg.swappiness_path, "r") as f:
                current = f.read().strip()
            log.info("Arbiter online. Current swappiness=%s path=%s",
                     current, self.cfg.swappiness_path)
        except PermissionError:
            raise RuntimeError(
                f"Cannot read {self.cfg.swappiness_path}. "
                "Run as root or grant CAP_SYS_ADMIN."
            )

    def apply(self, target: int) -> bool:
        target = max(0, min(200, int(target)))  # kernel accepts 0..200

        if target == self._last_written:
            return False  # no-op, avoid syscall churn

        if self.cfg.dry_run:
            log.info("[DRY-RUN] would set swappiness=%d (prev=%s)",
                     target, self._last_written)
            self._last_written = target
            return True

        try:
            with open(self.cfg.swappiness_path, "w") as f:
                f.write(str(target))
            log.info("Applied swappiness=%d (prev=%s)",
                     target, self._last_written)
            self._last_written = target
            return True
        except PermissionError:
            log.error("Permission denied writing %s. Run as root.",
                      self.cfg.swappiness_path)
            return False
        except OSError as e:
            log.error("Failed to write swappiness: %s", e)
            return False
