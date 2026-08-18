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
    CONF_EV_MAX_CURRENT,
    CONF_EV_PRIORITY,
    CONF_GRID_SETPOINT,
    CONF_HAS_EV,
    CONF_HAS_EV_CHARGER,
    CONF_HAS_GRID_CONNECTION,
    CONF_HAS_HOME_BATTERY,
    CONF_HAS_PV,
    CONF_HAS_SOC_LOADS,
    CONF_HOME_LOAD,
    CONF_MAX_GRID_POWER,
    CONF_PROFILE,
    CONF_PV_SAFETY_MARGIN,
    CONF_SOC_LOAD_OFF_THRESHOLD,
    CONF_SOC_LOAD_ON_THRESHOLD,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_ENABLE_EV_ACTUATION,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_PRIORITY,
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
    assert result["step_id"] == "energy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_GRID_SETPOINT: "number.grid_setpoint",
            CONF_HOME_LOAD: "sensor.home_load",
        },
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
    assert result["step_id"] == "settings"

    control_options = {
        CONF_MAX_GRID_POWER: 2900,
        CONF_ENABLE_ACTUATION: False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], control_options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GridPilot"
    assert result["options"] == control_options


async def test_selected_equipment_shows_matching_entity_steps(
    hass: HomeAssistant,
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PROFILE: PROFILE_GENERIC,
            CONF_HAS_GRID_CONNECTION: True,
            CONF_HAS_HOME_BATTERY: True,
            CONF_HAS_PV: True,
            CONF_HAS_EV: True,
            CONF_HAS_EV_CHARGER: True,
            CONF_HAS_SOC_LOADS: True,
        },
    )
    assert result["step_id"] == "energy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_GRID_SETPOINT: "number.grid_setpoint",
            CONF_HOME_LOAD: "sensor.home_load",
            "grid_power": "sensor.grid_power",
        },
    )
    assert result["step_id"] == "battery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_BATTERY_POWER: "sensor.battery_power",
        },
    )
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "charger"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "soc_load_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "soc_load_entity": "switch.flexible_load",
            CONF_SOC_LOAD_ON_THRESHOLD: "90",
            CONF_SOC_LOAD_OFF_THRESHOLD: "30",
        },
    )
    assert result["step_id"] == "soc_load_add"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"add_another_soc_load": False}
    )
    assert result["step_id"] == "settings"


async def test_grid_connection_and_home_battery_are_required(
    hass: HomeAssistant,
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PROFILE: PROFILE_GENERIC,
            CONF_HAS_GRID_CONNECTION: False,
            CONF_HAS_HOME_BATTERY: True,
            CONF_HAS_PV: False,
            CONF_HAS_EV: False,
            CONF_HAS_EV_CHARGER: False,
            CONF_HAS_SOC_LOADS: False,
        },
    )
    assert result["errors"] == {CONF_HAS_GRID_CONNECTION: "grid_connection_required"}


async def test_existing_entry_can_start_the_reconfigure_wizard(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PROFILE: PROFILE_GENERIC,
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_BATTERY_POWER: "sensor.battery_power",
            CONF_GRID_SETPOINT: "number.grid_setpoint",
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PROFILE: PROFILE_GENERIC,
            CONF_HAS_GRID_CONNECTION: True,
            CONF_HAS_HOME_BATTERY: True,
            CONF_HAS_PV: False,
            CONF_HAS_EV: False,
            CONF_HAS_EV_CHARGER: False,
            CONF_HAS_SOC_LOADS: False,
        },
    )
    assert result["step_id"] == "energy"


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
            CONF_GRID_SETPOINT: "number.grid_setpoint",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "load_entities_required"}


async def test_options_flow_starts_with_equipment_selection(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_ENABLE_ACTUATION: False,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert {key.schema for key in result["data_schema"].schema} == {
        CONF_PROFILE,
        CONF_HAS_GRID_CONNECTION,
        CONF_HAS_PV,
        CONF_HAS_HOME_BATTERY,
        CONF_HAS_EV,
        CONF_HAS_EV_CHARGER,
        CONF_HAS_SOC_LOADS,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PROFILE: PROFILE_GENERIC,
            CONF_HAS_GRID_CONNECTION: True,
            CONF_HAS_HOME_BATTERY: True,
            CONF_HAS_PV: False,
            CONF_HAS_EV: False,
            CONF_HAS_EV_CHARGER: False,
            CONF_HAS_SOC_LOADS: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "energy"


async def test_options_flow_prefills_existing_entity_mappings(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_MAX_GRID_POWER: 2900,
            CONF_CHARGE_SOC: 15,
            CONF_ENABLE_ACTUATION: False,
            "grid_power": "sensor.old_grid_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PROFILE: PROFILE_GENERIC,
            CONF_HAS_GRID_CONNECTION: True,
            CONF_HAS_HOME_BATTERY: True,
            CONF_HAS_PV: True,
            CONF_HAS_EV: False,
            CONF_HAS_EV_CHARGER: False,
            CONF_HAS_SOC_LOADS: False,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_GRID_SETPOINT: "number.grid_setpoint",
            CONF_HOME_LOAD: "sensor.home_load",
            "grid_power": "sensor.old_grid_power",
        },
    )

    assert result["step_id"] == "battery"


def _default_ev_options() -> dict[str, object]:
    return {
        CONF_BATTERY_CHARGE_POSITIVE: DEFAULT_BATTERY_CHARGE_POSITIVE,
        CONF_EV_PRIORITY: DEFAULT_EV_PRIORITY,
        CONF_EV_MAX_CURRENT: DEFAULT_EV_MAX_CURRENT,
        CONF_PV_SAFETY_MARGIN: DEFAULT_PV_SAFETY_MARGIN,
        CONF_ENABLE_EV_ACTUATION: DEFAULT_ENABLE_EV_ACTUATION,
    }
