"""Tests for the pure battery calculation engine."""

import pytest

from custom_components.gridpilot.calculations import (
    BatteryCurve,
    calculate_battery_decision,
    normalize_power,
)
from custom_components.gridpilot.const import (
    MODE_CHARGING,
    MODE_MAX_CHARGING,
    MODE_NEUTRAL,
    MODE_NORMAL,
    MODE_TAPERING,
)


@pytest.fixture
def curve() -> BatteryCurve:
    return BatteryCurve(
        charge_soc=15,
        minimum_charge_power=300,
    )


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (500, "W", 500),
        (1.5, "kW", 1500),
        (0.002, "MW", 2000),
        (2000, "mW", 2),
    ],
)
def test_normalize_power(value: float, unit: str, expected: float) -> None:
    assert normalize_power(value, unit) == expected


def test_normalize_power_rejects_unknown_unit() -> None:
    with pytest.raises(ValueError, match="Unsupported power unit"):
        normalize_power(10, "A")


@pytest.mark.parametrize(
    ("soc", "mode", "setpoint"),
    [
        (10, MODE_MAX_CHARGING, 2900),
        (12.5, MODE_CHARGING, 2900),
        (15, MODE_NEUTRAL, 1100),
        (17.5, MODE_TAPERING, 180),
        (20, MODE_NORMAL, 0),
        (80, MODE_NORMAL, 0),
    ],
)
def test_battery_curve_boundaries(
    curve: BatteryCurve, soc: float, mode: str, setpoint: float
) -> None:
    decision = calculate_battery_decision(
        soc=soc,
        home_load=1100,
        max_grid_power=2900,
        curve=curve,
    )
    assert decision.valid
    assert decision.mode == mode
    assert decision.requested_grid_setpoint == setpoint


def test_grid_limit_caps_home_load_and_charging(curve: BatteryCurve) -> None:
    decision = calculate_battery_decision(
        soc=9,
        home_load=4000,
        max_grid_power=2900,
        curve=curve,
    )
    assert decision.requested_grid_setpoint == 2900


@pytest.mark.parametrize("curve", [BatteryCurve(2, 300), BatteryCurve(98, 300)])
def test_invalid_curves_are_rejected(curve: BatteryCurve) -> None:
    with pytest.raises(ValueError, match="Charge SOC"):
        curve.validate()


def test_soc_thresholds_are_derived_from_charge_soc(curve: BatteryCurve) -> None:
    assert curve.minimum_soc == 12
    assert curve.normal_soc == 18
