"""Binary sensors provided by GridPilot."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class MeasurementsValidBinarySensor(GridPilotEntity, BinarySensorEntity):
    """Whether all inputs form a valid decision."""

    _attr_translation_key = "measurements_valid"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_measurements_valid"

    @property
    def is_on(self) -> bool:
        return self.controller.decision.valid


class ShadowModeBinarySensor(GridPilotEntity, BinarySensorEntity):
    """Whether GridPilot is calculating without writing."""

    _attr_translation_key = "shadow_mode"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_shadow_mode"

    @property
    def is_on(self) -> bool:
        return not self.controller.actuation_enabled


class ActuationHealthyBinarySensor(GridPilotEntity, BinarySensorEntity):
    """Whether active setpoint control is operating without an error."""

    _attr_translation_key = "actuation_healthy"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_actuation_healthy"

    @property
    def is_on(self) -> bool:
        return self.controller.actuation_healthy


class EVMeasurementsValidBinarySensor(GridPilotEntity, BinarySensorEntity):
    """Whether all EV inputs form a valid decision."""

    _attr_translation_key = "ev_measurements_valid"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_measurements_valid"

    @property
    def is_on(self) -> bool:
        return self.controller.ev_decision.valid


class EVShadowModeBinarySensor(GridPilotEntity, BinarySensorEntity):
    """Whether GridPilot calculates EV current without writing it."""

    _attr_translation_key = "ev_shadow_mode"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_shadow_mode"

    @property
    def is_on(self) -> bool:
        return not self.controller.ev_actuation_enabled


class EVActuationHealthyBinarySensor(GridPilotEntity, BinarySensorEntity):
    """Whether EV current actuation is operating without an error."""

    _attr_translation_key = "ev_actuation_healthy"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GridPilotConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_ev_actuation_healthy"

    @property
    def is_on(self) -> bool:
        return self.controller.ev_actuation_healthy


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot binary sensors."""
    async_add_entities(
        [
            MeasurementsValidBinarySensor(entry),
            ShadowModeBinarySensor(entry),
            ActuationHealthyBinarySensor(entry),
            EVMeasurementsValidBinarySensor(entry),
            EVShadowModeBinarySensor(entry),
            EVActuationHealthyBinarySensor(entry),
        ]
    )
