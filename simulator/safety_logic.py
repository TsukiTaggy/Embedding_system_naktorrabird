"""Gateway safety-state logic used by the simulator.

The Gateway firmware should later port the same rules (C++), so keep this
module small, readable, and free of I/O.

All threshold values in DEFAULT_THRESHOLDS are PLACEHOLDERS chosen to make the
simulator scenarios visible on the dashboard. They are NOT validated battery
safety limits. The team must agree on real values (software_checklist.md §1).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Deque, Optional, Tuple

STARTING = "STARTING"
NORMAL = "NORMAL"
WARNING = "WARNING"
HAZARD = "HAZARD"
SENSOR_ERROR = "SENSOR_ERROR"


@dataclass
class Thresholds:
    """Placeholder decision thresholds (see module docstring)."""

    warn_temp_c: float = 45.0
    hazard_temp_c: float = 55.0
    warn_rate_c_per_s: float = 0.2
    hazard_rate_c_per_s: float = 1.0
    warn_gas_raw: int = 1500
    hazard_gas_raw: int = 2500
    # Temperature-trend (dT/dt) settings
    rate_window_s: float = 10.0
    rate_min_samples: int = 5
    # A WARNING clears only after this many consecutive clear samples (hysteresis)
    warning_clear_samples: int = 5
    # Node data older than this is treated as stale (draft; not yet in the contract)
    node_stale_ms: int = 5000

    @classmethod
    def from_dict(cls, data: dict) -> "Thresholds":
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown threshold keys: {sorted(unknown)}")
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_THRESHOLDS = Thresholds()


@dataclass
class GatewayInputs:
    """Everything the Gateway knows at one decision step."""

    now_ms: int
    temp_bat_c: Optional[float]
    gas_raw: Optional[int]
    flame_detected: Optional[bool]
    node_age_ms: Optional[int]
    temp_ambient_c: Optional[float]
    humidity_pct: Optional[float]
    current_a: Optional[float]
    button_event: Optional[str] = None  # "STOP", "RESET" or None


@dataclass
class Decision:
    state: str
    power_cut: bool
    temp_rate_c_per_s: Optional[float]
    node_link_ok: bool
    reasons: list = field(default_factory=list)
    transition: Optional[str] = None  # human-readable "OLD -> NEW: why"


def linear_regression_slope(points: "list[Tuple[float, float]]") -> Optional[float]:
    """Least-squares slope dy/dx for (x, y) points; None if undefined."""
    n = len(points)
    if n < 2:
        return None
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mean_x) ** 2 for p in points)
    if sxx == 0:
        return None
    sxy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points)
    return sxy / sxx


class SafetyLogic:
    """Stateful decision maker: trend window, hysteresis, and latched power cut.

    Rules (in priority order):
      1. HAZARD is latched: once entered, power_cut stays true and the state stays
         HAZARD until a local RESET button event arrives while no hazard condition
         is present. A RESET during an active hazard is rejected and logged.
      2. A hazard condition (flame, temp >= hazard, dT/dt >= hazard, gas >= hazard)
         enters HAZARD and cuts power.
      3. Missing battery temperature or stale Node data -> SENSOR_ERROR.
         (Power is NOT cut automatically here; that behaviour is still undecided.)
      4. Not enough samples for dT/dt yet after boot -> STARTING (only once;
         later gaps in the trend just skip the dT/dt rules).
      5. A warning condition -> WARNING; it clears only after
         `warning_clear_samples` consecutive clear samples.
      6. Otherwise NORMAL.
    A STOP button event cuts power manually (latched) without changing the state
    rules; RESET clears a manual stop when no hazard is present.
    """

    def __init__(self, thresholds: Thresholds = DEFAULT_THRESHOLDS):
        self.t = thresholds
        self._temps: Deque[Tuple[float, float]] = deque()
        self.state = STARTING
        self._hazard_latched = False
        self._manual_stop = False
        self._clear_count = 0
        self._started = False  # becomes True after the first full trend window

    # -- trend ---------------------------------------------------------------
    def _update_rate(self, now_ms: int, temp: Optional[float]) -> Optional[float]:
        now_s = now_ms / 1000.0
        if temp is not None:
            self._temps.append((now_s, temp))
        while self._temps and now_s - self._temps[0][0] > self.t.rate_window_s:
            self._temps.popleft()
        if len(self._temps) < self.t.rate_min_samples:
            return None
        return linear_regression_slope(list(self._temps))

    # -- conditions ----------------------------------------------------------
    def _hazard_reasons(self, i: GatewayInputs, rate: Optional[float], node_ok: bool) -> list:
        r = []
        if node_ok and i.flame_detected:
            r.append("flame detected")
        if node_ok and i.temp_bat_c is not None and i.temp_bat_c >= self.t.hazard_temp_c:
            r.append(f"battery temp {i.temp_bat_c:.1f} >= {self.t.hazard_temp_c} C")
        if node_ok and rate is not None and rate >= self.t.hazard_rate_c_per_s:
            r.append(f"dT/dt {rate:+.2f} >= {self.t.hazard_rate_c_per_s} C/s")
        if node_ok and i.gas_raw is not None and i.gas_raw >= self.t.hazard_gas_raw:
            r.append(f"gas_raw {i.gas_raw} >= {self.t.hazard_gas_raw}")
        return r

    def _warning_reasons(self, i: GatewayInputs, rate: Optional[float]) -> list:
        r = []
        if i.temp_bat_c is not None and i.temp_bat_c >= self.t.warn_temp_c:
            r.append(f"battery temp {i.temp_bat_c:.1f} >= {self.t.warn_temp_c} C")
        if rate is not None and rate >= self.t.warn_rate_c_per_s:
            r.append(f"dT/dt {rate:+.2f} >= {self.t.warn_rate_c_per_s} C/s")
        if i.gas_raw is not None and i.gas_raw >= self.t.warn_gas_raw:
            r.append(f"gas_raw {i.gas_raw} >= {self.t.warn_gas_raw}")
        return r

    # -- main step -------------------------------------------------------------
    def step(self, i: GatewayInputs) -> Decision:
        node_ok = i.node_age_ms is not None and i.node_age_ms <= self.t.node_stale_ms
        # Only trust the battery temperature for the trend while the Node link is fresh.
        rate = self._update_rate(i.now_ms, i.temp_bat_c if node_ok else None)
        if not node_ok or i.temp_bat_c is None:
            rate = None

        hazard = self._hazard_reasons(i, rate, node_ok)
        reasons: list = []

        # Buttons
        if i.button_event == "STOP":
            self._manual_stop = True
            reasons.append("manual STOP button")
        elif i.button_event == "RESET":
            if hazard:
                reasons.append("RESET rejected: hazard still present")
            else:
                if self._hazard_latched or self._manual_stop:
                    reasons.append("RESET accepted (local button)")
                self._hazard_latched = False
                self._manual_stop = False

        if hazard:
            self._hazard_latched = True

        old = self.state
        if self._hazard_latched:
            new = HAZARD
            reasons += hazard or ["hazard latched; waiting for local RESET"]
        elif i.temp_bat_c is None or not node_ok:
            new = SENSOR_ERROR
            if not node_ok:
                age = "none" if i.node_age_ms is None else f"{i.node_age_ms} ms"
                reasons.append(f"Node data stale (age {age} > {self.t.node_stale_ms} ms)")
            if i.temp_bat_c is None:
                reasons.append("battery temperature unavailable")
        elif rate is None and not self._started:
            new = STARTING
            reasons.append("collecting samples for dT/dt")
        else:
            # After start-up, a temporarily missing trend (e.g. right after a sensor
            # recovers) does not send the system back to STARTING; the temperature
            # and gas rules still apply and the trend rules resume once data refills.
            self._started = True
            warn = self._warning_reasons(i, rate)
            if warn:
                new = WARNING
                self._clear_count = 0
                reasons += warn
            elif old == WARNING:
                self._clear_count += 1
                if self._clear_count >= self.t.warning_clear_samples:
                    new = NORMAL
                    reasons.append(f"clear for {self._clear_count} samples")
                else:
                    new = WARNING
                    reasons.append(
                        f"holding WARNING ({self._clear_count}/{self.t.warning_clear_samples} clear samples)"
                    )
            else:
                new = NORMAL

        if new != WARNING:
            self._clear_count = 0

        self.state = new
        transition = f"{old} -> {new}: {'; '.join(reasons) or 'conditions normal'}" if new != old else None
        return Decision(
            state=new,
            power_cut=self._hazard_latched or self._manual_stop,
            temp_rate_c_per_s=None if rate is None else round(rate, 3),
            node_link_ok=node_ok,
            reasons=reasons,
            transition=transition,
        )
