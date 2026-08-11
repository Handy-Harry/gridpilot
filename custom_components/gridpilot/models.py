"""Data models for GridPilot."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlDecision:
    """Result of one shadow-mode calculation."""

    valid: bool
    mode: str
    reason: str
    soc: float | None = None
    home_load: float | None = None
    max_grid_power: float | None = None
    requested_grid_setpoint: float | None = None


@dataclass(frozen=True, slots=True)
class EVControlDecision:
    """Result of one EV charging calculation."""

    valid: bool
    mode: str
    reason: str
    strategy: str = "none"
    battery_full: bool = False
    available_pv_power: float | None = None
    allocated_ev_power: float | None = None
    target_current: float | None = None
    requested_current: float | None = None
    phase_count: int | None = None
