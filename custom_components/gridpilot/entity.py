"""Base entity for GridPilot."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME, VERSION
from .runtime import GridPilotConfigEntry


class GridPilotEntity(Entity):
    """Base class for entities backed by the shadow controller."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        self.entry = entry
        self.controller = entry.runtime_data.controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="GridPilot",
            model="Energy orchestrator",
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.controller.async_add_listener(self.async_write_ha_state)
        )
