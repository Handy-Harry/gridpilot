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
    charging_only: bool = False,
) -> CapacitySample:
    """Return a baseline or smoothed capacity estimate from cumulative energy.

    EV calibration is charging-only because the vehicle's consumed energy is not
    available in Home Assistant. SOC updates can arrive in jumps, so the previous
    baseline is retained while a charging window is still too small to measure.
    """
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

    raw_soc_delta = soc - previous["soc"]
    raw_energy_delta = (
        charge_energy
        - previous["charge_energy"]
        - (discharge_energy - previous["discharge_energy"])
    )
    if charging_only and raw_soc_delta < 0:
        return {
            "soc": soc,
            "charge_energy": charge_energy,
            "discharge_energy": discharge_energy,
            "capacity": previous["capacity"],
        }

    soc_delta = raw_soc_delta if charging_only else abs(raw_soc_delta)
    energy_delta = raw_energy_delta if charging_only else abs(raw_energy_delta)
    if charging_only and (soc_delta <= 0 or energy_delta <= 0):
        return previous
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
