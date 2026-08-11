"""Pure GridPilot PV-surplus and EV-current calculations."""

from __future__ import annotations

import math

from .const import (
    BATTERY_FULL_RELEASE_SOC,
    BATTERY_FULL_SOC,
    EV_MIN_CURRENT,
    EV_MODE_CHARGING,
    EV_MODE_WAITING,
)
from .models import EVControlDecision


def update_battery_full_hysteresis(soc: float, battery_full: bool) -> bool:
    """Update the battery-full latch using the 98/97 percent thresholds."""
    if not math.isfinite(soc) or not 0 <= soc <= 100:
        raise ValueError("Battery SOC must be between 0 and 100 percent")
    if battery_full:
        return soc >= BATTERY_FULL_RELEASE_SOC
    return soc >= BATTERY_FULL_SOC


def calculate_available_pv_power(
    *,
    ev_power: float,
    battery_power: float,
    grid_power: float,
    safety_margin: float,
) -> float:
    """Return power that can be distributed without increasing grid import."""
    values = (ev_power, battery_power, grid_power, safety_margin)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("PV power inputs must be finite")
    if safety_margin < 0:
        raise ValueError("PV safety margin cannot be negative")
    return max(0.0, ev_power + battery_power - grid_power - safety_margin)


def calculate_ev_pv_decision(
    *,
    ev_power: float,
    battery_power: float,
    grid_power: float,
    voltage: float,
    phase_count: int,
    priority: float,
    max_current: float,
    safety_margin: float,
    battery_full: bool,
) -> EVControlDecision:
    """Calculate the unconstrained EV target current from available PV power."""
    if phase_count not in (1, 3):
        raise ValueError("EV phase count must be 1 or 3")
    if not math.isfinite(voltage) or voltage <= 0:
        raise ValueError("EV voltage must be positive")
    if not math.isfinite(priority) or not 0 <= priority <= 100:
        raise ValueError("EV priority must be between 0 and 100 percent")
    if not math.isfinite(max_current) or max_current < EV_MIN_CURRENT:
        raise ValueError("EV maximum current must be at least 6 A")

    available = calculate_available_pv_power(
        ev_power=ev_power,
        battery_power=battery_power,
        grid_power=grid_power,
        safety_margin=safety_margin,
    )
    share = 1.0 if battery_full else priority / 100
    allocated = available * share
    target = min(max_current, allocated / (voltage * phase_count))
    charging = target >= EV_MIN_CURRENT

    return EVControlDecision(
        valid=True,
        mode=EV_MODE_CHARGING if charging else EV_MODE_WAITING,
        reason=(
            "Available PV power supports EV charging"
            if charging
            else "Available PV power is below the minimum charging current"
        ),
        battery_full=battery_full,
        available_pv_power=round(available, 1),
        allocated_ev_power=round(allocated, 1),
        target_current=round(target, 2),
        phase_count=phase_count,
    )
