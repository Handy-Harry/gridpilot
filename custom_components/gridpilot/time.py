"""Time entities provided by GridPilot."""

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_EV_DEPARTURE_TIME, DEFAULT_EV_DEPARTURE_TIME
from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class EVDepartureTime(GridPilotEntity, TimeEntity):
    """Set the daily EV departure time used for charging planning."""

    _attr_translation_key = "ev_departure_time"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_departure_time"

    @property
    def native_value(self) -> time:
        return time.fromisoformat(
            str(
                self.entry.options.get(
                    CONF_EV_DEPARTURE_TIME, DEFAULT_EV_DEPARTURE_TIME
                )
            )
        )

    async def async_set_value(self, value: time) -> None:
        await self.controller.async_update_ev_option(
            CONF_EV_DEPARTURE_TIME, value.isoformat()
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot time entities."""
    async_add_entities([EVDepartureTime(entry)])
