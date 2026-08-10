"""Config and options flows for GridPilot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    CONF_PROFILE,
    DEFAULT_CHARGE_SOC,
    DEFAULT_MINIMUM_CHARGE_POWER,
    DEFAULT_MINIMUM_SOC,
    DEFAULT_NORMAL_SOC,
    DOMAIN,
    PROFILE_GENERIC,
    PROFILE_VICTRON,
)


def _entity_selector(domains: list[str]) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            filter=selector.EntityFilterSelectorConfig(domain=domains)
        )
    )


class GridPilotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the GridPilot setup flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a configuration profile."""
        if user_input is not None:
            await self.async_set_unique_id("home")
            self._abort_if_unique_id_configured()
            self._data.update(user_input)
            return await self.async_step_battery()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PROFILE, default=PROFILE_GENERIC
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[PROFILE_GENERIC, PROFILE_VICTRON],
                        translation_key="profile",
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the battery entities."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()

        victron = self._data.get(CONF_PROFILE) == PROFILE_VICTRON
        soc_key = vol.Required(
            CONF_BATTERY_SOC,
            default="sensor.gx_device_dc_battery_charge" if victron else vol.UNDEFINED,
        )
        power_key = vol.Required(
            CONF_BATTERY_POWER,
            default="sensor.gx_device_dc_battery_power" if victron else vol.UNDEFINED,
        )
        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    soc_key: _entity_selector(["sensor"]),
                    power_key: _entity_selector(["sensor"]),
                }
            ),
        )

    async def async_step_energy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect grid and home-load entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            has_total = bool(user_input.get(CONF_HOME_LOAD))
            has_phases = all(
                user_input.get(key)
                for key in (CONF_HOME_LOAD_L1, CONF_HOME_LOAD_L2, CONF_HOME_LOAD_L3)
            )
            if not has_total and not has_phases:
                errors["base"] = "load_entities_required"
            else:
                self._data.update(user_input)
                return self.async_create_entry(title="GridPilot", data=self._data)

        power_sources = ["sensor", "number"]
        victron = self._data.get(CONF_PROFILE) == PROFILE_VICTRON
        setpoint_key = vol.Required(
            CONF_GRID_SETPOINT,
            default="number.gx_device_ac_power_setpoint" if victron else vol.UNDEFINED,
        )
        l1_key = vol.Optional(
            CONF_HOME_LOAD_L1,
            default="sensor.gx_device_consumption_power_l1"
            if victron
            else vol.UNDEFINED,
        )
        l2_key = vol.Optional(
            CONF_HOME_LOAD_L2,
            default="sensor.gx_device_consumption_power_l2"
            if victron
            else vol.UNDEFINED,
        )
        l3_key = vol.Optional(
            CONF_HOME_LOAD_L3,
            default="sensor.gx_device_consumption_power_l3"
            if victron
            else vol.UNDEFINED,
        )
        schema = vol.Schema(
            {
                setpoint_key: _entity_selector(["number"]),
                vol.Required(CONF_MAX_GRID_POWER): _entity_selector(power_sources),
                vol.Optional(CONF_HOME_LOAD): _entity_selector(["sensor"]),
                l1_key: _entity_selector(["sensor"]),
                l2_key: _entity_selector(["sensor"]),
                l3_key: _entity_selector(["sensor"]),
            }
        )
        return self.async_show_form(step_id="energy", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GridPilotOptionsFlow:
        """Return the options flow."""
        return GridPilotOptionsFlow()


class GridPilotOptionsFlow(config_entries.OptionsFlow):
    """Configure the battery curve."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit SOC and charge-power options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (
                user_input[CONF_MINIMUM_SOC]
                < user_input[CONF_CHARGE_SOC]
                < user_input[CONF_NORMAL_SOC]
            ):
                errors["base"] = "invalid_soc_order"
            else:
                return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MINIMUM_SOC,
                    default=current.get(CONF_MINIMUM_SOC, DEFAULT_MINIMUM_SOC),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=98, step=0.5, unit_of_measurement="%"
                    )
                ),
                vol.Required(
                    CONF_CHARGE_SOC,
                    default=current.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=99, step=0.5, unit_of_measurement="%"
                    )
                ),
                vol.Required(
                    CONF_NORMAL_SOC,
                    default=current.get(CONF_NORMAL_SOC, DEFAULT_NORMAL_SOC),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=2, max=100, step=0.5, unit_of_measurement="%"
                    )
                ),
                vol.Required(
                    CONF_MINIMUM_CHARGE_POWER,
                    default=current.get(
                        CONF_MINIMUM_CHARGE_POWER, DEFAULT_MINIMUM_CHARGE_POWER
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10_000,
                        step=10,
                        unit_of_measurement="W",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
