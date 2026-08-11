"""Tests for pure GridPilot PV-surplus and EV-current calculations."""

import pytest

from custom_components.gridpilot.ev_calculations import (
    calculate_available_pv_power,
    calculate_ev_pv_decision,
    update_battery_full_hysteresis,
)


def test_available_pv_power_matches_existing_energy_balance() -> None:
    assert (
        calculate_available_pv_power(
            ev_power=2300,
            battery_power=1800,
            grid_power=100,
            safety_margin=200,
        )
        == 3800
    )


def test_available_pv_power_never_becomes_negative() -> None:
    assert (
        calculate_available_pv_power(
            ev_power=0,
            battery_power=-500,
            grid_power=300,
            safety_margin=100,
        )
        == 0
    )


def test_battery_full_hysteresis_uses_98_and_97_percent() -> None:
    assert not update_battery_full_hysteresis(97.9, False)
    assert update_battery_full_hysteresis(98, False)
    assert update_battery_full_hysteresis(97, True)
    assert not update_battery_full_hysteresis(96.9, True)


@pytest.mark.parametrize(
    ("phase_count", "expected_current"),
    [(1, 12.0), (3, 4.0)],
)
def test_ev_current_accounts_for_phase_count(
    phase_count: int, expected_current: float
) -> None:
    decision = calculate_ev_pv_decision(
        ev_power=0,
        battery_power=2760,
        grid_power=0,
        voltage=230,
        phase_count=phase_count,
        priority=100,
        max_current=16,
        safety_margin=0,
        battery_full=False,
    )

    assert decision.target_current == expected_current
    assert decision.phase_count == phase_count


def test_full_battery_assigns_all_available_power_to_ev() -> None:
    decision = calculate_ev_pv_decision(
        ev_power=0,
        battery_power=2300,
        grid_power=0,
        voltage=230,
        phase_count=1,
        priority=50,
        max_current=16,
        safety_margin=0,
        battery_full=True,
    )

    assert decision.allocated_ev_power == 2300
    assert decision.target_current == 10
