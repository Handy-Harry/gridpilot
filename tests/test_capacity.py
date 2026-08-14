"""Tests for persistent GridPilot capacity calibration."""

from custom_components.gridpilot.capacity import update_capacity_sample


def test_capacity_calibration_requires_meaningful_window() -> None:
    baseline = update_capacity_sample(
        None, soc=80, charge_energy=10, discharge_energy=5
    )
    unchanged = update_capacity_sample(
        baseline, soc=77, charge_energy=10, discharge_energy=6
    )

    assert baseline["capacity"] == 0
    assert unchanged == baseline


def test_capacity_calibration_learns_and_smooths_estimates() -> None:
    baseline = update_capacity_sample(
        None, soc=80, charge_energy=10, discharge_energy=5
    )
    learned = update_capacity_sample(
        baseline, soc=70, charge_energy=10, discharge_energy=11
    )
    smoothed = update_capacity_sample(
        learned, soc=60, charge_energy=10, discharge_energy=18
    )

    assert learned["capacity"] == 60
    assert smoothed["capacity"] == 62.5


def test_capacity_calibration_resets_baseline_when_meter_resets() -> None:
    previous = update_capacity_sample(
        None, soc=70, charge_energy=10, discharge_energy=11
    )
    previous["capacity"] = 60

    reset = update_capacity_sample(
        previous, soc=65, charge_energy=0, discharge_energy=0
    )

    assert reset == {
        "soc": 65,
        "charge_energy": 0,
        "discharge_energy": 0,
        "capacity": 60,
    }
