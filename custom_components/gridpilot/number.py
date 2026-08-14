"""Number entities provided by GridPilot."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_EV_BATTERY_CAPACITY,
    CONF_EV_DEPARTURE_TARGET_SOC,
    CONF_EV_PRIORITY,
    DEFAULT_EV_BATTERY_CAPACITY,
    DEFAULT_EV_DEPARTURE_TARGET_SOC,
    DEFAULT_EV_PRIORITY,
)
from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class EVPriorityNumber(GridPilotEntity, NumberEntity):
    """Control how available PV power is divided between battery and EV."""

    _attr_translation_key = "ev_priority"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:scale-balance"

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_priority"

    @property
    def native_value(self) -> float:
        """Return the configured EV share of available PV power."""
        return float(self.entry.options.get(CONF_EV_PRIORITY, DEFAULT_EV_PRIORITY))

    async def async_set_native_value(self, value: float) -> None:
        """Persist a new EV priority in the config entry."""
        await self.controller.async_update_ev_priority(value)


class EVDepartureTargetSOCNumber(GridPilotEntity, NumberEntity):
    """Set the required EV SOC at the configured departure time."""

    _attr_translation_key = "ev_departure_target_soc"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:battery-check"

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_departure_target_soc"

    @property
    def native_value(self) -> float:
        return float(
            self.entry.options.get(
                CONF_EV_DEPARTURE_TARGET_SOC, DEFAULT_EV_DEPARTURE_TARGET_SOC
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.controller.async_update_ev_option(
            CONF_EV_DEPARTURE_TARGET_SOC, value
        )


class EVBatteryCapacityNumber(GridPilotEntity, NumberEntity):
    """Set the usable EV battery capacity used for departure planning."""

    _attr_translation_key = "ev_battery_capacity"
    _attr_native_min_value = 1
    _attr_native_max_value = 200
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:car-electric"

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_battery_capacity"

    @property
    def native_value(self) -> float:
        return float(
            self.entry.options.get(
                CONF_EV_BATTERY_CAPACITY, DEFAULT_EV_BATTERY_CAPACITY
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.controller.async_update_ev_option(CONF_EV_BATTERY_CAPACITY, value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot number entities."""
    async_add_entities(
        [
            EVPriorityNumber(entry),
            EVDepartureTargetSOCNumber(entry),
            EVBatteryCapacityNumber(entry),
        ]
    )
