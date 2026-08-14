"""Persistent battery capacity calibration helpers."""

from __future__ import annotations

import math
from typing import TypedDict

from .const import CAPACITY_MIN_ENERGY_DELTA, CAPACITY_MIN_SOC_DELTA, CAPACITY_SMOOTHING


class CapacitySample(TypedDict):
    soc: float
    charge_energy: float
    discharge_energy: float
    capacity: float


def update_capacity_sample(
    previous: CapacitySample | None,
    *,
    soc: float,
    charge_energy: float,
    discharge_energy: float,
) -> CapacitySample:
    """Return a baseline or a smoothed capacity estimate from cumulative energy."""
    if not all(
        math.isfinite(value) for value in (soc, charge_energy, discharge_energy)
    ):
        raise ValueError("Capacity calibration inputs must be finite")
    if not 0 <= soc <= 100 or charge_energy < 0 or discharge_energy < 0:
        raise ValueError("Capacity calibration inputs are invalid")
    if previous is None or (
        charge_energy < previous["charge_energy"]
        or discharge_energy < previous["discharge_energy"]
    ):
        return {
            "soc": soc,
            "charge_energy": charge_energy,
            "discharge_energy": discharge_energy,
            "capacity": previous["capacity"] if previous else 0.0,
        }

    soc_delta = abs(soc - previous["soc"])
    energy_delta = abs(
        (charge_energy - previous["charge_energy"])
        - (discharge_energy - previous["discharge_energy"])
    )
    if soc_delta < CAPACITY_MIN_SOC_DELTA or energy_delta < CAPACITY_MIN_ENERGY_DELTA:
        return previous

    estimate = energy_delta * 100 / soc_delta
    capacity = (
        estimate
        if previous["capacity"] <= 0
        else previous["capacity"] * (1 - CAPACITY_SMOOTHING)
        + estimate * CAPACITY_SMOOTHING
    )
    return {
        "soc": soc,
        "charge_energy": charge_energy,
        "discharge_energy": discharge_energy,
        "capacity": round(capacity, 2),
    }
