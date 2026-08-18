"""Pure GridPilot PV-surplus and EV-current calculations."""

from __future__ import annotations

import math

from .const import (
    BATTERY_FULL_RELEASE_SOC,
    BATTERY_FULL_SOC,
    EV_BATTERY_MIN_TOLERANCE,
    EV_CHARGING_EFFICIENCY,
    EV_CURRENT_STEP,
    EV_MIN_CURRENT,
    EV_MODE_CHARGING,
    EV_MODE_WAITING,
    EV_PAUSE_CURRENT,
    EV_STRATEGY_BATTERY_TO_EV,
    EV_STRATEGY_DEPARTURE,
    EV_STRATEGY_MANUAL,
    EV_STRATEGY_PV,
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
        strategy=EV_STRATEGY_PV,
        battery_full=battery_full,
        available_pv_power=round(available, 1),
        allocated_ev_power=round(allocated, 1),
        target_current=round(target, 2),
        phase_count=phase_count,
    )


def calculate_manual_ev_decision(
    *, requested_current: float, max_current: float
) -> EVControlDecision:
    """Validate and return the current selected for manual charging."""
    if not math.isfinite(requested_current):
        raise ValueError("Manual EV current must be finite")
    if not math.isfinite(max_current) or max_current < EV_MIN_CURRENT:
        raise ValueError("EV maximum current must be at least 6 A")
    if requested_current < EV_MIN_CURRENT or requested_current > max_current:
        raise ValueError(f"Manual EV current must be between 6 and {max_current:g} A")
    return EVControlDecision(
        valid=True,
        mode=EV_MODE_CHARGING,
        reason="EV current follows the manual charging setting",
        strategy=EV_STRATEGY_MANUAL,
        target_current=round(requested_current, 2),
        requested_current=round(requested_current, 2),
    )


def calculate_battery_to_ev_decision(
    *,
    current: float,
    battery_soc: float,
    secondary_soc: float,
    minimum_soc: float,
    time_to_go: float,
    seconds_until_target: float,
    max_current: float,
) -> EVControlDecision:
    """Calculate EV current that reaches the battery reserve near the deadline."""
    values = (
        current,
        battery_soc,
        secondary_soc,
        minimum_soc,
        time_to_go,
        seconds_until_target,
        max_current,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Battery-to-EV inputs must be finite")
    if not all(0 <= soc <= 100 for soc in (battery_soc, secondary_soc)):
        raise ValueError("Battery SOC must be between 0 and 100 percent")
    if not 0 <= minimum_soc < 100:
        raise ValueError("Battery-to-EV minimum SOC must be below 100 percent")
    if max_current < EV_MIN_CURRENT:
        raise ValueError("EV maximum current must be at least 6 A")
    if battery_soc <= minimum_soc or secondary_soc <= minimum_soc:
        return EVControlDecision(
            valid=True,
            mode=EV_MODE_WAITING,
            reason="Battery reserve SOC pauses battery-to-EV charging",
            strategy=EV_STRATEGY_BATTERY_TO_EV,
            target_current=EV_PAUSE_CURRENT,
            requested_current=EV_PAUSE_CURRENT,
        )
    if time_to_go <= 0 or seconds_until_target <= 0:
        raise ValueError("Battery-to-EV timing inputs must be positive")

    desired_time_to_go = (
        seconds_until_target * secondary_soc / (secondary_soc - minimum_soc)
    )
    tolerance = max(EV_BATTERY_MIN_TOLERANCE, desired_time_to_go * 0.05)
    if current < EV_MIN_CURRENT:
        requested = EV_MIN_CURRENT
        reason = "Battery-to-EV charging started"
    elif time_to_go > desired_time_to_go + tolerance:
        requested = current + EV_CURRENT_STEP
        reason = "Battery reserve allows more EV current"
    elif time_to_go < desired_time_to_go - tolerance and current > EV_MIN_CURRENT:
        requested = current - EV_CURRENT_STEP
        reason = "Battery reserve requires less EV current"
    else:
        requested = current
        reason = "Battery-to-EV current is within the target tolerance"

    requested = min(max_current, max(EV_MIN_CURRENT, requested))
    return EVControlDecision(
        valid=True,
        mode=EV_MODE_CHARGING,
        reason=reason,
        strategy=EV_STRATEGY_BATTERY_TO_EV,
        target_current=round(requested, 2),
        requested_current=round(requested, 2),
    )


def calculate_departure_ev_decision(
    *,
    vehicle_soc: float,
    target_soc: float,
    battery_capacity_kwh: float,
    seconds_until_departure: float,
    voltage: float,
    phase_count: int,
    max_current: float,
) -> EVControlDecision:
    """Plan the EV current needed to reach its target SOC by departure."""
    values = (
        vehicle_soc,
        target_soc,
        battery_capacity_kwh,
        seconds_until_departure,
        voltage,
        max_current,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Departure charging inputs must be finite")
    if not 0 <= vehicle_soc <= 100 or not 0 <= target_soc <= 100:
        raise ValueError("EV SOC must be between 0 and 100 percent")
    if battery_capacity_kwh <= 0:
        raise ValueError("EV battery capacity must be positive")
    if seconds_until_departure <= 0:
        raise ValueError("Departure time must be in the future")
    if phase_count not in (1, 3) or voltage <= 0:
        raise ValueError("EV voltage and phase count are invalid")
    if max_current < EV_MIN_CURRENT:
        raise ValueError("EV maximum current must be at least 6 A")

    if vehicle_soc >= target_soc:
        return EVControlDecision(
            valid=True,
            mode=EV_MODE_WAITING,
            reason="EV target SOC has been reached",
            strategy=EV_STRATEGY_DEPARTURE,
            target_current=EV_PAUSE_CURRENT,
            requested_current=EV_PAUSE_CURRENT,
            phase_count=phase_count,
        )

    needed_wh = (
        battery_capacity_kwh
        * 1000
        * (target_soc - vehicle_soc)
        / 100
        / EV_CHARGING_EFFICIENCY
    )
    required_power = needed_wh * 3600 / seconds_until_departure
    power_per_amp = voltage * phase_count
    required_current = required_power / power_per_amp
    requested = min(max_current, max(EV_MIN_CURRENT, required_current))
    if required_current > max_current:
        reason = "EV target SOC cannot be reached by departure time"
    else:
        reason = "EV current is planned for the departure time"
    return EVControlDecision(
        valid=True,
        mode=EV_MODE_CHARGING,
        reason=reason,
        strategy=EV_STRATEGY_DEPARTURE,
        target_current=round(required_current, 2),
        requested_current=round(requested, 2),
        phase_count=phase_count,
    )
