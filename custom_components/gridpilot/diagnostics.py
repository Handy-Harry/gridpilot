"""Diagnostics for GridPilot."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_SOC,
    CONF_EV_BATTERY_TARGET_TIME,
    CONF_EV_BATTERY_TIME_TO_GO,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_MODE,
    CONF_EV_OVERRIDE,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_VOLTAGE,
    CONF_GRID_POWER,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
)
from .runtime import GridPilotConfigEntry

TO_REDACT = {
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_GRID_POWER,
    CONF_EV_POWER,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_VOLTAGE,
    CONF_EV_PHASE_MODE,
    CONF_EV_MODE,
    CONF_EV_OVERRIDE,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_BATTERY_SOC,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_TIME_TO_GO,
    CONF_EV_BATTERY_TARGET_TIME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GridPilotConfigEntry
) -> dict[str, Any]:
    """Return privacy-preserving diagnostics."""
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "runtime": entry.runtime_data.controller.diagnostics,
    }
