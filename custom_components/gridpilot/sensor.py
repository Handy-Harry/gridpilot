"""Sensors provided by GridPilot."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_BATTERY_ENERGY,
    CONF_EV_BATTERY_CAPACITY,
    CONF_EV_DEPARTURE_TARGET_SOC,
    CONF_EV_VEHICLE_SOC,
    DEFAULT_EV_BATTERY_CAPACITY,
    DEFAULT_EV_DEPARTURE_TARGET_SOC,
    EV_CONTROL_MODES,
    EV_STRATEGIES,
    MODES,
)
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
        return self.controller.decision.calculated_grid_setpoint


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


class DepartureBatteryPowerSensor(GridPilotEntity, SensorEntity):
    """Show home-battery power planned for departure-time charging."""

    _attr_translation_key = "departure_battery_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_departure_battery_power"

    @property
    def native_value(self) -> float | None:
        return self.controller.departure_battery_power


class HomeBatteryEnergySensor(GridPilotEntity, SensorEntity):
    """Expose the configured measured remaining home-battery energy."""

    _attr_translation_key = "home_battery_energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_home_battery_energy"

    @property
    def native_value(self) -> float | None:
        capacity = self.controller.learned_capacity("home")
        if capacity is not None:
            try:
                return round(
                    capacity
                    * self.controller._numeric_state(self.entry.data["battery_soc"])
                    / 100,
                    2,
                )
            except ValueError:
                pass
        entity_id = self.entry.options.get(CONF_BATTERY_ENERGY)
        if isinstance(entity_id, str):
            try:
                return round(self.controller._energy_state(entity_id), 2)
            except ValueError:
                pass
        return None


class EVBatteryEnergySensor(GridPilotEntity, SensorEntity):
    """Calculate the current EV battery energy from SOC and usable capacity."""

    _attr_translation_key = "ev_battery_energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_battery_energy"

    @property
    def native_value(self) -> float | None:
        entity_id = self.entry.options.get(CONF_EV_VEHICLE_SOC)
        if not isinstance(entity_id, str):
            return None
        try:
            soc = self.controller._numeric_state(entity_id)
            capacity = self.controller.learned_capacity("ev") or float(
                self.entry.options.get(
                    CONF_EV_BATTERY_CAPACITY, DEFAULT_EV_BATTERY_CAPACITY
                )
            )
        except ValueError:
            return None
        return round(capacity * soc / 100, 2)


class EVEnergyToTargetSensor(GridPilotEntity, SensorEntity):
    """Calculate EV energy still required to reach the departure target."""

    _attr_translation_key = "ev_energy_to_target"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_energy_to_target"

    @property
    def native_value(self) -> float | None:
        entity_id = self.entry.options.get(CONF_EV_VEHICLE_SOC)
        if not isinstance(entity_id, str):
            return None
        try:
            soc = self.controller._numeric_state(entity_id)
            capacity = self.controller.learned_capacity("ev") or float(
                self.entry.options.get(
                    CONF_EV_BATTERY_CAPACITY, DEFAULT_EV_BATTERY_CAPACITY
                )
            )
            target = float(
                self.entry.options.get(
                    CONF_EV_DEPARTURE_TARGET_SOC, DEFAULT_EV_DEPARTURE_TARGET_SOC
                )
            )
        except ValueError:
            return None
        return round(capacity * max(0, target - soc) / 100, 2)


class HomeBatteryCapacitySensor(GridPilotEntity, SensorEntity):
    """Expose GridPilot's learned usable home-battery capacity."""

    _attr_translation_key = "home_battery_capacity"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_home_battery_capacity"

    @property
    def native_value(self) -> float | None:
        return self.controller.learned_capacity("home")


class EVBatteryCapacitySensor(GridPilotEntity, SensorEntity):
    """Expose GridPilot's learned usable EV battery capacity."""

    _attr_translation_key = "ev_battery_capacity_learned"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_battery_capacity_learned"

    @property
    def native_value(self) -> float | None:
        return self.controller.learned_capacity("ev")


class EVOperatingModeSensor(GridPilotEntity, SensorEntity):
    """Current calculated EV control mode."""

    _attr_translation_key = "ev_operating_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = EV_CONTROL_MODES

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_operating_mode"

    @property
    def native_value(self) -> str:
        return self.controller.ev_decision.mode


class EVStrategySensor(GridPilotEntity, SensorEntity):
    """Selected GridPilot EV charging strategy."""

    _attr_translation_key = "ev_strategy"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = EV_STRATEGIES

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_strategy"

    @property
    def native_value(self) -> str:
        return self.controller.ev_decision.strategy


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
            DepartureBatteryPowerSensor(entry),
            HomeBatteryEnergySensor(entry),
            EVBatteryEnergySensor(entry),
            EVEnergyToTargetSensor(entry),
            HomeBatteryCapacitySensor(entry),
            EVBatteryCapacitySensor(entry),
            EVOperatingModeSensor(entry),
            EVStrategySensor(entry),
            EVControlReasonSensor(entry),
        ]
    )
