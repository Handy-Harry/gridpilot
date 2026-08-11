"""GridPilot integration setup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .calculations import normalize_power
from .const import (
    CONF_CHARGE_SOC,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    DEFAULT_CHARGE_SOC,
    DEFAULT_MINIMUM_CHARGE_POWER,
    DEFAULT_MINIMUM_SOC,
    DEFAULT_NORMAL_SOC,
    VERSION,
)
from .const import DOMAIN as DOMAIN

FRONTEND_PATH = Path(__file__).parent / "frontend"
BRAND_PATH = Path(__file__).parent / "brand"
FRONTEND_URL = f"/gridpilot_static/gridpilot-card.js?v={VERSION}"
DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .runtime import GridPilotConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled frontend once."""
    return await _async_setup_frontend(hass)


async def _async_setup_frontend(hass: HomeAssistant) -> bool:
    """Serve and announce the card module for new and existing frontend sessions."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    if not hass.data.get(DATA_FRONTEND_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig("/gridpilot_static", str(FRONTEND_PATH), False),
                StaticPathConfig("/gridpilot_brand", str(BRAND_PATH), False),
            ]
        )
        hass.data[DATA_FRONTEND_REGISTERED] = True

    add_extra_js_url(hass, FRONTEND_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Set up GridPilot from a config entry."""
    from homeassistant.const import Platform

    from .controller import GridPilotController
    from .runtime import GridPilotRuntime

    await _async_setup_frontend(hass)
    platforms = [Platform.SENSOR, Platform.BINARY_SENSOR]
    controller = GridPilotController(hass, entry)
    entry.runtime_data = GridPilotRuntime(controller=controller)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await controller.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: GridPilotConfigEntry
) -> bool:
    """Move version 1 control parameters into config-entry options."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        data = dict(entry.data)
        options = dict(entry.options)
        legacy_max_grid_power = data.get(CONF_MAX_GRID_POWER)

        if CONF_MAX_GRID_POWER not in options:
            migrated_max_grid_power = _legacy_max_grid_power(
                hass, legacy_max_grid_power
            )
            if migrated_max_grid_power is not None:
                options[CONF_MAX_GRID_POWER] = migrated_max_grid_power
                data.pop(CONF_MAX_GRID_POWER, None)
        else:
            data.pop(CONF_MAX_GRID_POWER, None)

        defaults = {
            CONF_MINIMUM_SOC: DEFAULT_MINIMUM_SOC,
            CONF_CHARGE_SOC: DEFAULT_CHARGE_SOC,
            CONF_NORMAL_SOC: DEFAULT_NORMAL_SOC,
            CONF_MINIMUM_CHARGE_POWER: DEFAULT_MINIMUM_CHARGE_POWER,
        }
        for key, value in defaults.items():
            options.setdefault(key, value)

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=2,
            minor_version=1,
        )

    return True


def _legacy_max_grid_power(hass: HomeAssistant, value: Any) -> float | None:
    """Convert a legacy entity mapping or numeric value to persistent watts."""
    if isinstance(value, int | float):
        return max(0.0, float(value))
    if isinstance(value, str) and (state := hass.states.get(value)) is not None:
        try:
            return max(
                0.0,
                normalize_power(
                    float(state.state), state.attributes.get("unit_of_measurement")
                ),
            )
        except (TypeError, ValueError):
            pass
    return None


async def async_unload_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Unload GridPilot."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry[Any]) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
