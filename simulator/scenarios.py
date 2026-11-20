"""Scripted, repeatable test scenarios for the virtual Gateway.

Each scenario returns the "physical world" at simulated time t (seconds):
what the sensors would see, whether links are up, and any button press.
Profiles are scripted by time, so they do not react to the simulated power
cut (except charging current, which the Gateway model forces to ~0 when cut).

All numbers are illustrative values for exercising the dashboard and logic,
not real battery behaviour or validated limits.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class World:
    temp_bat_c: float
    gas_raw: float
    flame: bool
    temp_ambient_c: float
    humidity_pct: float
    charge_current_a: float          # current that flows when power is NOT cut
    temp_sensor_ok: bool = True      # DS18B20 returns a reading
    node_link_up: bool = True        # ESP-NOW messages reach the Gateway
    cloud_link_up: bool = True       # Gateway Wi-Fi / NETPIE connection
    button: Optional[str] = None     # "STOP", "RESET" or None at this instant


@dataclass
class Scenario:
    name: str
    description: str
    duration_s: float
    world: Callable[..., World]  # world(t_s, rng, dt) -> World


def _n(rng: random.Random, sigma: float) -> float:
    return rng.gauss(0.0, sigma)


def _baseline(t: float, rng: random.Random, temp: float = 31.5, gas: float = 800.0) -> World:
    return World(
        temp_bat_c=temp + _n(rng, 0.08),
        gas_raw=gas + _n(rng, 15),
        flame=False,
        temp_ambient_c=28.0 + _n(rng, 0.1),
        humidity_pct=64.0 + _n(rng, 0.5),
        charge_current_a=1.40 + _n(rng, 0.03),
    )


def _cooling(t: float, t0: float, start: float, target: float = 33.0, tau: float = 12.0) -> float:
    return target + (start - target) * math.exp(-(t - t0) / tau)


def _at(t: float, when: float, dt: float) -> bool:
    """True on the single step where `when` falls in [t, t + dt)."""
    return t <= when < t + dt


# --- scenario profiles -------------------------------------------------------

def normal(t, rng, dt=1.0):
    return _baseline(t, rng)


def gradual_rise(t, rng, dt=1.0):
    return _baseline(t, rng, temp=32.0 + 0.12 * t)


def _rapid_temp(t: float) -> float:
    if t < 15:
        return 35.0
    if t < 22:
        return 35.0 + 2.0 * (t - 15)            # +2 C/s
    return _cooling(t, 22, 49.0)


def rapid_rise(t, rng, dt=1.0):
    w = _baseline(t, rng, temp=_rapid_temp(t), gas=800 + (400 if t >= 18 else 0))
    return w


def over_temp(t, rng, dt=1.0):
    temp = 40.0 + 0.3 * t if t < 60 else 58.0
    return _baseline(t, rng, temp=temp)


def gas_flame(t, rng, dt=1.0):
    gas = 800.0 if t < 10 else min(2000.0, 800.0 + 60.0 * (t - 10))
    w = _baseline(t, rng, gas=gas)
    w.flame = 35 <= t < 43
    return w


def sensor_fault(t, rng, dt=1.0):
    w = _baseline(t, rng)
    w.temp_sensor_ok = not (20 <= t < 35)
    return w


def node_stale(t, rng, dt=1.0):
    w = _baseline(t, rng)
    w.node_link_up = not (20 <= t < 35)
    return w


def network_loss(t, rng, dt=1.0):
    w = _baseline(t, rng)
    w.cloud_link_up = not (20 <= t < 40)
    return w


def button_reset(t, rng, dt=1.0):
    temp = 35.0 if t < 10 else (35.0 + 2.0 * (t - 10) if t < 17 else _cooling(t, 17, 49.0))
    w = _baseline(t, rng, temp=temp)
    w.flame = 15 <= t < 35
    for when, ev in ((28, "RESET"), (50, "RESET"), (65, "STOP"), (78, "RESET")):
        if _at(t, when, dt):
            w.button = ev
    return w


SCENARIOS: Dict[str, Scenario] = {
    s.name: s
    for s in (
        Scenario("normal", "Stable charging, all sensors valid", 60, normal),
        Scenario("gradual_rise", "Battery temp rises 0.12 C/s; WARNING by temperature", 150, gradual_rise),
        Scenario("rapid_rise", "Temp jumps 35 -> 49 C at 2 C/s; HAZARD by dT/dt, latched", 60, rapid_rise),
        Scenario("over_temp", "Temp climbs 0.3 C/s to 58 C; WARNING then HAZARD by temperature", 90, over_temp),
        Scenario("gas_flame", "Gas raw rises to WARNING level, then a flame event causes HAZARD", 60, gas_flame),
        Scenario("sensor_fault", "DS18B20 returns no reading from t=20 to 35 s", 60, sensor_fault),
        Scenario("node_stale", "ESP-NOW link lost from t=20 to 35 s", 60, node_stale),
        Scenario("network_loss", "Gateway cloud link lost t=20-40 s; messages queued and replayed", 60, network_loss),
        Scenario("button_reset", "HAZARD with flame; RESET rejected, RESET accepted, STOP, RESET", 90, button_reset),
    )
}
