"""Tests for optional GridPilot battery actuation."""

from datetime import datetime
from time import time
from zoneinfo import ZoneInfo

from homeassistant.const import ATTR_ENTITY_ID, UnitOfElectricCurrent, UnitOfPower
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gridpilot import controller as controller_module
from custom_components.gridpilot.const import (
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_ENABLE_EV_ACTUATION,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_SOC,
    CONF_EV_BATTERY_TARGET_TIME,
    CONF_EV_BATTERY_TIME_TO_GO,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_VOLTAGE,
    CONF_GRID_POWER,
    CONF_GRID_SETPOINT,
    CONF_GRIDPILOT_EV_MODE,
    CONF_HOME_LOAD,
    CONF_MAX_GRID_POWER,
    DOMAIN,
)
from custom_components.gridpilot.controller import GridPilotController


def _entry(
    enable_actuation: bool,
    *,
    configure_ev: bool = False,
    enable_ev_actuation: bool = False,
    partial_ev: bool = False,
    battery_charge_positive: bool = True,
    current_feedback: bool = False,
    configure_manual: bool = False,
    configure_battery_to_ev: bool = False,
    pv_mode: str | None = None,
) -> MockConfigEntry:
    options = {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 15,
        CONF_ENABLE_ACTUATION: enable_actuation,
    }
    if partial_ev:
        options.update(
            {
                CONF_ENABLE_EV_ACTUATION: enable_ev_actuation,
                CONF_EV_CURRENT_LIMIT: "number.ev_current",
            }
        )
    elif (
        configure_ev
        or enable_ev_actuation
        or configure_manual
        or configure_battery_to_ev
    ):
        options.update(
            {
                CONF_BATTERY_CHARGE_POSITIVE: battery_charge_positive,
                CONF_ENABLE_EV_ACTUATION: enable_ev_actuation,
                CONF_GRID_POWER: "sensor.grid_power",
                CONF_EV_POWER: "sensor.ev_power",
                CONF_EV_CONNECTION_STATE: "sensor.ev_connection",
                CONF_EV_CURRENT_LIMIT: "number.ev_current",
                CONF_EV_VOLTAGE: "sensor.ev_voltage",
                CONF_EV_PHASE_MODE: "select.ev_phases",
            }
        )
        if current_feedback:
            options[CONF_EV_CURRENT_FEEDBACK] = "sensor.ev_current_feedback"
        if configure_manual:
            options[CONF_EV_MANUAL_CURRENT] = "input_number.manual_current"
        if configure_battery_to_ev:
            options.update(
                {
                    CONF_EV_BATTERY_SOC: "sensor.secondary_battery_soc",
                    CONF_EV_BATTERY_MIN_SOC: "input_number.minimum_battery_soc",
                    CONF_EV_BATTERY_TIME_TO_GO: "sensor.battery_time_to_go",
                    CONF_EV_BATTERY_TARGET_TIME: "input_datetime.battery_target",
                }
            )
        options[CONF_GRIDPILOT_EV_MODE] = pv_mode or "PV laden"
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_BATTERY_POWER: "sensor.battery_power",
            CONF_HOME_LOAD: "sensor.home_load",
            CONF_GRID_SETPOINT: "number.grid_setpoint",
        },
        options=options,
    )


def _set_valid_states(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.battery_soc", "15")
    hass.states.async_set(
        "sensor.home_load", "1100", {"unit_of_measurement": UnitOfPower.WATT}
    )
    hass.states.async_set(
        "number.grid_setpoint",
        "0",
        {"min": -10000, "max": 10000, "unit_of_measurement": UnitOfPower.WATT},
    )


def _set_ev_states(hass: HomeAssistant, *, mode: str = "PV laden") -> None:
    hass.states.async_set("sensor.battery_soc", "50")
    hass.states.async_set(
        "sensor.battery_power", "3680", {"unit_of_measurement": UnitOfPower.WATT}
    )
    hass.states.async_set(
        "sensor.grid_power", "0", {"unit_of_measurement": UnitOfPower.WATT}
    )
    hass.states.async_set(
        "sensor.ev_power", "0", {"unit_of_measurement": UnitOfPower.WATT}
    )
    hass.states.async_set("sensor.ev_connection", "Connected")
    hass.states.async_set("sensor.ev_voltage", "230", {"unit_of_measurement": "V"})
    hass.states.async_set("select.ev_phases", "1 Phase")
    hass.states.async_set(
        "number.ev_current",
        "5",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )


def _set_manual_ev_state(hass: HomeAssistant, current: float = 10) -> None:
    hass.states.async_set(
        "input_number.manual_current",
        str(current),
        {"unit_of_measurement": UnitOfElectricCurrent.AMPERE},
    )


def _set_battery_to_ev_states(
    hass: HomeAssistant,
    *,
    enabled: bool = True,
    primary_soc: float = 70,
    secondary_soc: float = 70,
    minimum_soc: float = 30,
) -> None:
    hass.states.async_set("sensor.battery_soc", str(primary_soc))
    hass.states.async_set("input_boolean.battery_to_ev", "on" if enabled else "off")
    hass.states.async_set("sensor.secondary_battery_soc", str(secondary_soc))
    hass.states.async_set("input_number.minimum_battery_soc", str(minimum_soc))
    hass.states.async_set(
        "sensor.battery_time_to_go",
        "75600",
        {"unit_of_measurement": "s"},
    )
    hass.states.async_set(
        "input_datetime.battery_target",
        "2026-08-12 08:00:00",
        {"timestamp": time() + 43_200},
    )


async def test_shadow_mode_never_writes(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(False))
    await controller.async_refresh()

    assert controller.decision.valid
    assert not controller.actuation_enabled
    assert calls == []


async def test_active_control_writes_calculated_setpoint(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(True))
    await controller.async_refresh()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "number.grid_setpoint",
        "value": 1100,
    }
    assert controller.last_applied_setpoint == 1100
    assert controller.actuation_healthy


async def test_invalid_measurements_apply_safe_zero(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    hass.states.async_set("sensor.battery_soc", "unknown")
    hass.states.async_set(
        "number.grid_setpoint",
        "1100",
        {"min": -10000, "max": 10000, "unit_of_measurement": UnitOfPower.WATT},
    )
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(True))
    await controller.async_refresh()

    assert not controller.decision.valid
    assert len(calls) == 1
    assert calls[0].data["value"] == 0
    assert controller.last_applied_setpoint == 0


async def test_active_control_rate_limits_normal_updates(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(True))
    await controller.async_refresh()
    hass.states.async_set(
        "sensor.home_load", "1200", {"unit_of_measurement": UnitOfPower.WATT}
    )
    await controller.async_refresh()

    assert len(calls) == 1


async def test_active_control_converts_watts_to_target_unit(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set(
        "number.grid_setpoint",
        "0",
        {"min": -10, "max": 10, "unit_of_measurement": UnitOfPower.KILO_WATT},
    )
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(True))
    await controller.async_refresh()

    assert len(calls) == 1
    assert calls[0].data["value"] == 1.1


async def test_failed_neutral_reset_disarms_controller(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set("number.grid_setpoint", "unavailable")
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    controller = GridPilotController(hass, _entry(True))

    assert not await controller.async_shutdown()
    assert not controller.actuation_enabled
    assert not controller.actuation_healthy

    hass.states.async_set(
        "number.grid_setpoint",
        "1100",
        {"min": -10000, "max": 10000, "unit_of_measurement": UnitOfPower.WATT},
    )
    await controller.async_refresh()
    assert len(calls) == 1
    assert calls[0].data["value"] == 0
    assert controller.actuation_healthy


async def test_ev_shadow_mode_calculates_without_writing(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    entry = _entry(False, configure_ev=True)
    _set_ev_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, entry)
    await controller.async_refresh()

    assert controller.ev_decision.valid
    assert controller.ev_decision.requested_current == 6
    assert calls == []


async def test_manual_ev_actuation_writes_configured_current(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Manueel")
    _set_manual_ev_state(hass, 10)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(
        hass,
        _entry(
            False,
            enable_ev_actuation=True,
            configure_manual=True,
            pv_mode="Manueel",
        ),
    )
    await controller.async_refresh()

    assert controller.ev_decision.strategy == "manual"
    assert controller.ev_decision.requested_current == 10
    assert calls[0].data == {
        ATTR_ENTITY_ID: "number.ev_current",
        "value": 10,
    }


async def test_inactive_ev_mode_does_not_write(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Uit")
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(
        hass, _entry(False, enable_ev_actuation=True, pv_mode="Uit")
    )
    await controller.async_refresh()

    assert controller.ev_decision.strategy == "none"
    assert controller.ev_decision.requested_current is None
    assert calls == []


async def test_strategy_change_bypasses_normal_ev_rate_limit(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="PV laden")
    _set_manual_ev_state(hass, 10)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    controller = GridPilotController(
        hass,
        _entry(
            False,
            enable_ev_actuation=True,
            configure_manual=True,
        ),
    )

    await controller.async_refresh()
    hass.states.async_set(
        "number.ev_current",
        "6",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    controller.entry.add_to_hass(hass)
    await controller.async_update_ev_mode("Manueel")

    assert [call.data["value"] for call in calls] == [6, 10]


async def test_strategy_change_starts_from_measured_current(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Manueel")
    _set_manual_ev_state(hass, 10)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    controller = GridPilotController(
        hass,
        _entry(
            False,
            enable_ev_actuation=True,
            configure_manual=True,
            pv_mode="Manueel",
        ),
    )

    await controller.async_refresh()
    hass.states.async_set(
        "number.ev_current",
        "10",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    controller.entry.add_to_hass(hass)
    await controller.async_update_ev_mode("PV laden")

    assert controller.ev_decision.requested_current == 9.9
    assert [call.data["value"] for call in calls] == [10, 9.9]


async def test_battery_to_ev_toggle_does_not_override_pv_mode(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="PV laden")
    _set_battery_to_ev_states(hass)
    controller = GridPilotController(
        hass,
        _entry(False, configure_battery_to_ev=True),
    )

    await controller.async_refresh()

    assert controller.ev_decision.valid
    assert controller.ev_decision.strategy == "pv"


async def test_battery_to_ev_toggle_is_explicit_when_mode_is_not_pv_or_manual(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Thuisbatterij naar EV")
    _set_battery_to_ev_states(hass)
    controller = GridPilotController(
        hass,
        _entry(False, configure_battery_to_ev=True, pv_mode="Thuisbatterij naar EV"),
    )

    await controller.async_refresh()

    assert controller.ev_decision.valid
    assert controller.ev_decision.strategy == "battery_to_ev"
    assert controller.ev_decision.requested_current == 6


async def test_battery_to_ev_reserve_soc_forces_safe_pause(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Manueel")
    _set_battery_to_ev_states(hass, secondary_soc=30)
    hass.states.async_set(
        "number.ev_current",
        "8",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    controller = GridPilotController(
        hass,
        _entry(
            False,
            enable_ev_actuation=True,
            configure_battery_to_ev=True,
            pv_mode="Thuisbatterij naar EV",
        ),
    )

    await controller.async_refresh()

    assert controller.ev_decision.requested_current == 5
    assert calls[0].data["value"] == 5


async def test_battery_to_ev_handoff_preserves_measured_current(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Uit")
    _set_manual_ev_state(hass, 16)
    _set_battery_to_ev_states(hass, enabled=False)
    hass.states.async_set(
        "number.ev_current",
        "16",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    controller = GridPilotController(
        hass,
        _entry(
            False,
            configure_manual=True,
            configure_battery_to_ev=True,
        ),
    )

    await controller.async_refresh()
    hass.states.async_set("input_boolean.battery_to_ev", "on")
    controller.entry.add_to_hass(hass)
    await controller.async_update_ev_mode("Thuisbatterij naar EV")

    assert controller.ev_decision.strategy == "battery_to_ev"
    assert controller.ev_decision.requested_current == 16


async def test_battery_to_ev_handoff_to_pv_calculates_from_measured_current(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Thuisbatterij naar EV")
    _set_battery_to_ev_states(hass)
    controller = GridPilotController(
        hass,
        _entry(False, configure_battery_to_ev=True, pv_mode="Thuisbatterij naar EV"),
    )

    await controller.async_refresh()
    hass.states.async_set("input_boolean.battery_to_ev", "off")
    hass.states.async_set(
        "sensor.battery_power", "0", {"unit_of_measurement": UnitOfPower.WATT}
    )
    hass.states.async_set(
        "number.ev_current",
        "6",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    controller.entry.add_to_hass(hass)
    await controller.async_update_ev_mode("PV laden")

    assert controller.ev_decision.strategy == "pv"
    assert controller.ev_decision.mode == "stop_delay"
    assert controller.ev_decision.requested_current == 6


async def test_battery_reserve_pause_bypasses_ev_rate_limit(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass, mode="Thuisbatterij naar EV")
    _set_battery_to_ev_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    controller = GridPilotController(
        hass,
        _entry(
            False,
            enable_ev_actuation=True,
            configure_battery_to_ev=True,
            pv_mode="Thuisbatterij naar EV",
        ),
    )

    await controller.async_refresh()
    hass.states.async_set(
        "number.ev_current",
        "6",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    hass.states.async_set("sensor.secondary_battery_soc", "30")
    await controller.async_refresh()

    assert [call.data["value"] for call in calls] == [6, 5]


async def test_disconnect_pause_bypasses_ev_rate_limit(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    controller = GridPilotController(
        hass,
        _entry(False, enable_ev_actuation=True),
    )

    await controller.async_refresh()
    hass.states.async_set(
        "number.ev_current",
        "6",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    hass.states.async_set("sensor.ev_connection", "Available")
    await controller.async_refresh()

    assert [call.data["value"] for call in calls] == [6, 5]


def test_time_only_deadline_uses_local_time_and_dst(
    hass: HomeAssistant, monkeypatch
) -> None:
    zone = ZoneInfo("Europe/Brussels")
    monkeypatch.setattr(
        controller_module.dt_util,
        "now",
        lambda: datetime(2026, 3, 28, 9, 0, tzinfo=zone),
    )
    hass.states.async_set(
        "input_datetime.battery_target",
        "08:00:00",
        {
            "has_date": False,
            "has_time": True,
            "hour": 8,
            "minute": 0,
            "second": 0,
            "timestamp": 28_800,
        },
    )
    controller = GridPilotController(hass, _entry(False))

    assert controller._seconds_until_target("input_datetime.battery_target") == 79_200


async def test_ev_actuation_starts_at_six_amps(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(False, enable_ev_actuation=True))
    await controller.async_refresh()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: "number.ev_current",
        "value": 6,
    }


async def test_ev_actuation_rejects_actuator_without_safe_pause(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    hass.states.async_set(
        "number.ev_current",
        "6",
        {
            "min": 6,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(hass, _entry(False, enable_ev_actuation=True))
    await controller.async_refresh()

    assert not controller.ev_decision.valid
    assert "safe 5 A pause" in controller.ev_decision.reason
    assert controller.last_ev_actuation_error is not None
    assert calls == []


async def test_incomplete_active_ev_config_applies_safe_pause(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set(
        "number.ev_current",
        "10",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)

    controller = GridPilotController(
        hass,
        _entry(False, enable_ev_actuation=True, partial_ev=True),
    )
    await controller.async_refresh()

    assert not controller.ev_decision.valid
    assert calls[0].data == {
        ATTR_ENTITY_ID: "number.ev_current",
        "value": 5,
    }


async def test_ev_shutdown_uses_original_actuator_after_options_change(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    hass.states.async_set(
        "number.ev_current",
        "8",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    hass.states.async_set(
        "number.new_ev_current",
        "9",
        {
            "min": 0,
            "max": 32,
            "unit_of_measurement": UnitOfElectricCurrent.AMPERE,
        },
    )
    calls: list[ServiceCall] = []
    hass.services.async_register("number", "set_value", calls.append)
    entry = _entry(False, enable_ev_actuation=True)
    entry.add_to_hass(hass)
    controller = GridPilotController(hass, entry)
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_EV_CURRENT_LIMIT: "number.new_ev_current"},
    )

    assert await controller.async_shutdown()
    assert calls[0].data == {
        ATTR_ENTITY_ID: "number.ev_current",
        "value": 5,
    }


async def test_ev_current_feedback_drives_ramping(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    hass.states.async_set(
        "sensor.ev_current_feedback",
        "8",
        {"unit_of_measurement": UnitOfElectricCurrent.AMPERE},
    )
    controller = GridPilotController(
        hass,
        _entry(False, configure_ev=True, current_feedback=True),
    )

    await controller.async_refresh()
    await controller.async_refresh()

    assert controller.ev_decision.valid
    assert controller.ev_decision.requested_current == 8


async def test_ev_readback_above_configured_maximum_is_clamped(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    hass.states.async_set(
        "sensor.ev_current_feedback",
        "20",
        {"unit_of_measurement": UnitOfElectricCurrent.AMPERE},
    )
    controller = GridPilotController(
        hass,
        _entry(False, configure_ev=True, current_feedback=True),
    )

    await controller.async_refresh()
    await controller.async_refresh()

    assert controller.ev_decision.valid
    assert controller.ev_decision.requested_current == 16


async def test_ev_current_feedback_requires_amperes(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    hass.states.async_set(
        "sensor.ev_current_feedback",
        "8000",
        {"unit_of_measurement": "mA"},
    )
    controller = GridPilotController(
        hass,
        _entry(False, configure_ev=True, current_feedback=True),
    )

    await controller.async_refresh()

    assert not controller.ev_decision.valid
    assert "not measured in A" in controller.ev_decision.reason


async def test_negative_battery_charge_polarity_is_normalized(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    _set_ev_states(hass)
    hass.states.async_set(
        "sensor.battery_power", "-3680", {"unit_of_measurement": UnitOfPower.WATT}
    )
    controller = GridPilotController(
        hass,
        _entry(
            False,
            configure_ev=True,
            battery_charge_positive=False,
        ),
    )

    await controller.async_refresh()

    assert controller.ev_decision.valid
    assert controller.ev_decision.requested_current == 6
