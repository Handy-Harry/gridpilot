"""Diagnostics for GridPilot."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
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
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GridPilotConfigEntry
) -> dict[str, Any]:
    """Return privacy-preserving diagnostics."""
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "runtime": entry.runtime_data.controller.diagnostics,
    }
