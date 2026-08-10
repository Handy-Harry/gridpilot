"""Sensors provided by GridPilot."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODES
from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class GridSetpointSensor(GridPilotEntity, SensorEntity):
    """Calculated, read-only grid setpoint."""

    _attr_translation_key = "calculated_grid_setpoint"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_calculated_grid_setpoint"

    @property
    def native_value(self) -> float | None:
        return self.controller.decision.requested_grid_setpoint


class OperatingModeSensor(GridPilotEntity, SensorEntity):
    """Current calculated operating mode."""

    _attr_translation_key = "operating_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = MODES

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_operating_mode"

    @property
    def native_value(self) -> str:
        return self.controller.decision.mode


class ControlReasonSensor(GridPilotEntity, SensorEntity):
    """Human-readable reason for the current decision."""

    _attr_translation_key = "control_reason"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_control_reason"

    @property
    def native_value(self) -> str:
        return self.controller.decision.reason


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot sensors."""
    async_add_entities(
        [
            GridSetpointSensor(entry),
            OperatingModeSensor(entry),
            ControlReasonSensor(entry),
        ]
    )
