"""Tests for the GridPilot config flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.gridpilot.const import (
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_MAX_GRID_POWER,
    CONF_PROFILE,
    DOMAIN,
    PROFILE_GENERIC,
)


async def test_complete_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE: PROFILE_GENERIC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "battery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_BATTERY_POWER: "sensor.battery_power",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "energy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_GRID_SETPOINT: "number.grid_setpoint",
            CONF_MAX_GRID_POWER: "sensor.max_grid_power",
            CONF_HOME_LOAD: "sensor.home_load",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GridPilot"


async def test_load_entity_is_required(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROFILE: PROFILE_GENERIC},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_BATTERY_POWER: "sensor.battery_power",
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_GRID_SETPOINT: "number.grid_setpoint",
            CONF_MAX_GRID_POWER: "sensor.max_grid_power",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "load_entities_required"}
