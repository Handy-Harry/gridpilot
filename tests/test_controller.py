"""Tests for optional GridPilot battery actuation."""

from homeassistant.const import ATTR_ENTITY_ID, UnitOfPower
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gridpilot.const import (
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    DOMAIN,
)
from custom_components.gridpilot.controller import GridPilotController


def _entry(enable_actuation: bool) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_HOME_LOAD: "sensor.home_load",
            CONF_GRID_SETPOINT: "number.grid_setpoint",
        },
        options={
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_MINIMUM_CHARGE_POWER: 300,
            CONF_ENABLE_ACTUATION: enable_actuation,
        },
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
