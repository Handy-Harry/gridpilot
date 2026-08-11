"""Sensors provided by GridPilot."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EV_MODES, MODES
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


class AvailablePVPowerSensor(GridPilotEntity, SensorEntity):
    """PV power currently available to EV control."""

    _attr_translation_key = "available_pv_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_available_pv_power"

    @property
    def native_value(self) -> float | None:
        return self.controller.ev_decision.available_pv_power


class EVTargetCurrentSensor(GridPilotEntity, SensorEntity):
    """Calculated EV current after hysteresis and ramping."""

    _attr_translation_key = "ev_target_current"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_target_current"

    @property
    def native_value(self) -> float | None:
        return self.controller.ev_decision.requested_current


class EVOperatingModeSensor(GridPilotEntity, SensorEntity):
    """Current calculated EV control mode."""

    _attr_translation_key = "ev_operating_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = EV_MODES

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_operating_mode"

    @property
    def native_value(self) -> str:
        return self.controller.ev_decision.mode


class EVControlReasonSensor(GridPilotEntity, SensorEntity):
    """Human-readable reason for the EV decision."""

    _attr_translation_key = "ev_control_reason"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_control_reason"

    @property
    def native_value(self) -> str:
        return self.controller.ev_decision.reason


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
            AvailablePVPowerSensor(entry),
            EVTargetCurrentSensor(entry),
            EVOperatingModeSensor(entry),
            EVControlReasonSensor(entry),
        ]
    )
