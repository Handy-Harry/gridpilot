"""Tests for the GridPilot config flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gridpilot.const import (
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_ENABLE_EV_ACTUATION,
    CONF_EV_DISCONNECTED_STATE,
    CONF_EV_MANUAL_MODE,
    CONF_EV_MAX_CURRENT,
    CONF_EV_PRIORITY,
    CONF_EV_PV_MODE,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_PROFILE,
    CONF_PV_SAFETY_MARGIN,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_ENABLE_EV_ACTUATION,
    DEFAULT_EV_DISCONNECTED_STATE,
    DEFAULT_EV_MANUAL_MODE,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_PRIORITY,
    DEFAULT_EV_PV_MODE,
    DEFAULT_PV_SAFETY_MARGIN,
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
            CONF_HOME_LOAD: "sensor.home_load",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ev"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "control"

    control_options = {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 15,
        CONF_MINIMUM_CHARGE_POWER: 300,
        CONF_ENABLE_ACTUATION: False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], control_options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GridPilot"
    assert result["options"] == {**_default_ev_options(), **control_options}


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
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "load_entities_required"}


async def test_options_flow_updates_control_parameters(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_MINIMUM_CHARGE_POWER: 300,
            CONF_ENABLE_ACTUATION: False,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert {key.schema for key in result["data_schema"].schema} == {
        CONF_MAX_GRID_POWER,
        CONF_CHARGE_SOC,
        CONF_MINIMUM_CHARGE_POWER,
        CONF_ENABLE_ACTUATION,
    }

    updated = {
        CONF_MAX_GRID_POWER: 3500,
        CONF_CHARGE_SOC: 16,
        CONF_MINIMUM_CHARGE_POWER: 400,
        CONF_ENABLE_ACTUATION: True,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], updated
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ev"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**updated, **_default_ev_options()}


async def test_options_flow_can_clear_optional_ev_mapping(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_MINIMUM_CHARGE_POWER: 300,
            CONF_ENABLE_ACTUATION: False,
            "grid_power": "sensor.old_grid_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_MINIMUM_CHARGE_POWER: 300,
            CONF_ENABLE_ACTUATION: False,
        },
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "grid_power" not in result["data"]


async def test_options_flow_rejects_identical_ev_mode_values(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_MINIMUM_CHARGE_POWER: 300,
            CONF_ENABLE_ACTUATION: False,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_EV_PV_MODE: "Same mode",
            CONF_EV_MANUAL_MODE: "Same mode",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_EV_MANUAL_MODE: "mode_values_must_differ"}


def _default_ev_options() -> dict[str, object]:
    return {
        CONF_BATTERY_CHARGE_POSITIVE: DEFAULT_BATTERY_CHARGE_POSITIVE,
        CONF_EV_PV_MODE: DEFAULT_EV_PV_MODE,
        CONF_EV_MANUAL_MODE: DEFAULT_EV_MANUAL_MODE,
        CONF_EV_DISCONNECTED_STATE: DEFAULT_EV_DISCONNECTED_STATE,
        CONF_EV_PRIORITY: DEFAULT_EV_PRIORITY,
        CONF_EV_MAX_CURRENT: DEFAULT_EV_MAX_CURRENT,
        CONF_PV_SAFETY_MARGIN: DEFAULT_PV_SAFETY_MARGIN,
        CONF_ENABLE_EV_ACTUATION: DEFAULT_ENABLE_EV_ACTUATION,
    }
