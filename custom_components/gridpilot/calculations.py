"""Pure GridPilot calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .const import (
    MODE_CHARGING,
    MODE_MAX_CHARGING,
    MODE_NEUTRAL,
    MODE_NORMAL,
    MODE_TAPERING,
)
from .models import ControlDecision


@dataclass(frozen=True, slots=True)
class BatteryCurve:
    """Configurable battery control curve."""

    minimum_soc: float
    charge_soc: float
    normal_soc: float
    minimum_charge_power: float

    def validate(self) -> None:
        """Raise when the curve is unsafe or inconsistent."""
        if not 0 <= self.minimum_soc < self.charge_soc < self.normal_soc <= 100:
            raise ValueError(
                "SOC thresholds must satisfy 0 <= minimum < charge < normal <= 100"
            )
        if self.minimum_charge_power < 0:
            raise ValueError("Minimum charge power cannot be negative")


def normalize_power(value: float, unit: str | None) -> float:
    """Normalize a power value to watts."""
    normalized_unit = (unit or "W").strip().lower()
    if normalized_unit == "w":
        return value
    if normalized_unit == "kw":
        return value * 1_000
    if normalized_unit == "mw":
        return value * 1_000_000
    raise ValueError(f"Unsupported power unit: {unit}")


def calculate_battery_decision(
    *,
    soc: float,
    home_load: float,
    max_grid_power: float,
    curve: BatteryCurve,
) -> ControlDecision:
    """Calculate the desired grid setpoint without performing any writes."""
    curve.validate()
    if not all(math.isfinite(value) for value in (soc, home_load, max_grid_power)):
        raise ValueError("Inputs must be finite")
    if not 0 <= soc <= 100:
        raise ValueError("SOC must be between 0 and 100")
    if max_grid_power < 0:
        raise ValueError("Maximum grid power cannot be negative")

    load = max(0.0, home_load)

    if soc >= curve.normal_soc:
        requested = 0.0
        mode = MODE_NORMAL
        reason = "SOC is at or above the normal threshold"
    elif soc > curve.charge_soc:
        grid_share = (
            load * (curve.normal_soc - soc) / (curve.normal_soc - curve.charge_soc)
        )
        requested = min(max_grid_power, grid_share)
        mode = MODE_TAPERING
        reason = "Grid compensation tapers linearly toward zero"
    elif math.isclose(soc, curve.charge_soc, abs_tol=0.001):
        requested = min(max_grid_power, load)
        mode = MODE_NEUTRAL
        reason = "Grid setpoint compensates the home load"
    else:
        if soc <= curve.minimum_soc:
            proportional_charge = max_grid_power
            mode = MODE_MAX_CHARGING
            reason = "SOC is at or below the minimum threshold"
        else:
            proportional_charge = (
                max_grid_power
                * (curve.charge_soc - soc)
                / (curve.charge_soc - curve.minimum_soc)
            )
            mode = MODE_CHARGING
            reason = "Charge power rises as SOC approaches the minimum threshold"

        charge_power = max(curve.minimum_charge_power, proportional_charge)
        requested = min(max_grid_power, load + charge_power)

    rounded = round(requested / 10) * 10
    return ControlDecision(
        valid=True,
        mode=mode,
        reason=reason,
        soc=round(soc, 3),
        home_load=round(load, 1),
        max_grid_power=round(max_grid_power, 1),
        requested_grid_setpoint=float(rounded),
    )
