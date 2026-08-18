"""Switch entities provided by GridPilot."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_PRELOAD,
    DEFAULT_PRELOAD,
)
from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class PreloadSwitch(GridPilotEntity, SwitchEntity):
    """Enable forecast-based preloading of the home battery."""

    _attr_translation_key = "preload"
    _attr_icon = "mdi:battery-clock"

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_preload"

    @property
    def is_on(self) -> bool:
        """Return whether this automatic mode is enabled."""
        return bool(self.entry.options.get(CONF_PRELOAD, DEFAULT_PRELOAD))

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable forecast-based preloading."""
        await self.controller.async_update_preload(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable forecast-based preloading."""
        await self.controller.async_update_preload(False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot switches."""
    async_add_entities(
        [
            PreloadSwitch(entry),
        ]
    )
