"""Tests for pure GridPilot PV-surplus and EV-current calculations."""

import pytest

from custom_components.gridpilot.ev_calculations import (
    calculate_available_pv_power,
    calculate_battery_to_ev_decision,
    calculate_ev_pv_decision,
    calculate_manual_ev_decision,
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


def test_manual_ev_current_follows_selected_setting() -> None:
    decision = calculate_manual_ev_decision(requested_current=10.5, max_current=16)

    assert decision.strategy == "manual"
    assert decision.requested_current == 10.5


def test_manual_ev_current_rejects_values_below_charging_minimum() -> None:
    with pytest.raises(ValueError, match="between 6 and 16 A"):
        calculate_manual_ev_decision(requested_current=5, max_current=16)


def test_battery_to_ev_pauses_at_either_reserve_soc() -> None:
    decision = calculate_battery_to_ev_decision(
        current=8,
        battery_soc=30,
        secondary_soc=70,
        minimum_soc=30,
        time_to_go=60_000,
        seconds_until_target=36_000,
        grid_power=0,
        max_current=16,
    )

    assert decision.strategy == "battery_to_ev"
    assert decision.requested_current == 5


@pytest.mark.parametrize(
    ("grid_power", "time_to_go", "expected"),
    [
        (200, 75_600, 7.9),
        (0, 100_000, 8.1),
        (0, 50_000, 7.9),
        (0, 75_600, 8),
    ],
)
def test_battery_to_ev_adjusts_in_tenth_amp_steps(
    grid_power: float, time_to_go: float, expected: float
) -> None:
    decision = calculate_battery_to_ev_decision(
        current=8,
        battery_soc=70,
        secondary_soc=70,
        minimum_soc=30,
        time_to_go=time_to_go,
        seconds_until_target=43_200,
        grid_power=grid_power,
        max_current=16,
    )

    assert decision.requested_current == expected
