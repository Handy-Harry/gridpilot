"""Switch entities provided by GridPilot."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_AUTO_CHARGE_SOC_SOLAR,
    CONF_AUTO_CHARGE_SOC_SOLAR_EV,
    DEFAULT_AUTO_CHARGE_SOC_SOLAR,
    DEFAULT_AUTO_CHARGE_SOC_SOLAR_EV,
)
from .entity import GridPilotEntity
from .runtime import GridPilotConfigEntry


class AutoChargeSOCSwitch(GridPilotEntity, SwitchEntity):
    """Enable one automatic charge-SOC calculation mode."""

    def __init__(
        self,
        entry: GridPilotConfigEntry,
        option: str,
        translation_key: str,
        default: bool,
        icon: str,
    ) -> None:
        super().__init__(entry)
        self._option = option
        self._default = default
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{option}"
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        """Return whether this automatic mode is enabled."""
        return bool(self.entry.options.get(self._option, self._default))

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable this automatic mode and disable the other one."""
        await self.controller.async_update_auto_charge_soc_mode(self._option, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable this automatic mode."""
        await self.controller.async_update_auto_charge_soc_mode(self._option, False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GridPilot switches."""
    async_add_entities(
        [
            AutoChargeSOCSwitch(
                entry,
                CONF_AUTO_CHARGE_SOC_SOLAR,
                "auto_charge_soc_solar",
                DEFAULT_AUTO_CHARGE_SOC_SOLAR,
                "mdi:weather-sunny",
            ),
            AutoChargeSOCSwitch(
                entry,
                CONF_AUTO_CHARGE_SOC_SOLAR_EV,
                "auto_charge_soc_solar_ev",
                DEFAULT_AUTO_CHARGE_SOC_SOLAR_EV,
                "mdi:car-electric",
            ),
        ]
    )
