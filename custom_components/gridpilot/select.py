"""Select entities provided by GridPilot."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_GRIDPILOT_EV_MODE, DEFAULT_EV_MODE, EV_MODE_OPTIONS
from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class EVModeSelect(GridPilotEntity, SelectEntity):
    """Select the GridPilot-owned EV charging strategy."""

    _attr_translation_key = "ev_mode"
    _attr_options = EV_MODE_OPTIONS
    _attr_icon = "mdi:ev-station"

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_mode"

    @property
    def current_option(self) -> str:
        """Return the selected EV charging mode."""
        return str(self.entry.options.get(CONF_GRIDPILOT_EV_MODE, DEFAULT_EV_MODE))

    async def async_select_option(self, option: str) -> None:
        """Persist the selected EV charging mode."""
        await self.controller.async_update_ev_mode(option)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot selects."""
    async_add_entities([EVModeSelect(entry)])
