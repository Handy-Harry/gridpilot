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
