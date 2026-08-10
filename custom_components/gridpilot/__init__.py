"""GridPilot integration setup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .const import DOMAIN as DOMAIN
from .const import VERSION

FRONTEND_PATH = Path(__file__).parent / "frontend"
FRONTEND_URL = f"/gridpilot_static/gridpilot-card.js?v={VERSION}"

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .runtime import GridPilotConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled frontend once."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig("/gridpilot_static", str(FRONTEND_PATH), False)]
    )
    add_extra_js_url(hass, FRONTEND_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Set up GridPilot from a config entry."""
    from homeassistant.const import Platform

    from .controller import GridPilotController
    from .runtime import GridPilotRuntime

    platforms = [Platform.SENSOR, Platform.BINARY_SENSOR]
    controller = GridPilotController(hass, entry)
    entry.runtime_data = GridPilotRuntime(controller=controller)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await controller.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Unload GridPilot."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry[Any]) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
