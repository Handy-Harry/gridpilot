"""Config and options flows for GridPilot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_ENABLE_EV_ACTUATION,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_MODE,
    CONF_EV_BATTERY_SOC,
    CONF_EV_BATTERY_TARGET_TIME,
    CONF_EV_BATTERY_TIME_TO_GO,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_DISCONNECTED_STATE,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_MANUAL_MODE,
    CONF_EV_MAX_CURRENT,
    CONF_EV_MODE,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_PRIORITY,
    CONF_EV_PV_MODE,
    CONF_EV_VOLTAGE,
    CONF_GRID_POWER,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_PROFILE,
    CONF_PV_SAFETY_MARGIN,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_CHARGE_SOC,
    DEFAULT_ENABLE_ACTUATION,
    DEFAULT_ENABLE_EV_ACTUATION,
    DEFAULT_EV_BATTERY_MODE,
    DEFAULT_EV_DISCONNECTED_STATE,
    DEFAULT_EV_MANUAL_MODE,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_PRIORITY,
    DEFAULT_EV_PV_MODE,
    DEFAULT_MAX_GRID_POWER,
    DEFAULT_MINIMUM_CHARGE_POWER,
    DEFAULT_PV_SAFETY_MARGIN,
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

    VERSION = 6
    MINOR_VERSION = 0

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

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
                return await self.async_step_ev()

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
                vol.Optional(CONF_HOME_LOAD): _entity_selector(["sensor"]),
                l1_key: _entity_selector(["sensor"]),
                l2_key: _entity_selector(["sensor"]),
                l3_key: _entity_selector(["sensor"]),
            }
        )
        return self.async_show_form(step_id="energy", data_schema=schema, errors=errors)

    async def async_step_ev(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect optional PV-surplus and EV control mappings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _ev_options_errors(user_input)
            if not errors:
                self._options.update(user_input)
                return await self.async_step_control()

        return self.async_show_form(
            step_id="ev",
            data_schema=_ev_options_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the initial control parameters."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(
                title="GridPilot", data=self._data, options=self._options
            )

        return self.async_show_form(
            step_id="control",
            data_schema=_control_options_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GridPilotOptionsFlow:
        """Return the options flow."""
        return GridPilotOptionsFlow()


class GridPilotOptionsFlow(config_entries.OptionsFlow):
    """Configure the battery curve."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit SOC and charge-power options."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_ev()

        return self.async_show_form(
            step_id="init",
            data_schema=_control_options_schema(self.config_entry.options),
        )

    async def async_step_ev(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit PV-surplus and EV-current options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _ev_options_errors(user_input)
            if not errors:
                self._options.update(user_input)
                return self.async_create_entry(title="", data=self._options)

        return self.async_show_form(
            step_id="ev",
            data_schema=_ev_options_schema(user_input or self.config_entry.options),
            errors=errors,
        )


def _control_options_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the shared schema for persistent control parameters."""
    return vol.Schema(
        {
            vol.Required(
                CONF_MAX_GRID_POWER,
                default=current.get(CONF_MAX_GRID_POWER, DEFAULT_MAX_GRID_POWER),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10_000,
                    step=100,
                    unit_of_measurement="W",
                )
            ),
            vol.Required(
                CONF_CHARGE_SOC,
                default=current.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=95, step=0.5, unit_of_measurement="%"
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
            vol.Required(
                CONF_ENABLE_ACTUATION,
                default=current.get(CONF_ENABLE_ACTUATION, DEFAULT_ENABLE_ACTUATION),
            ): selector.BooleanSelector(),
        }
    )


def _ev_options_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the optional PV-surplus and EV-current schema."""

    def optional_entity(key: str, domains: list[str]) -> tuple[Any, Any]:
        marker = (
            vol.Optional(
                key,
                description={"suggested_value": current[key]},
            )
            if key in current
            else vol.Optional(key)
        )
        return marker, _entity_selector(domains)

    fields = dict(
        [
            optional_entity(CONF_GRID_POWER, ["sensor"]),
            optional_entity(CONF_EV_POWER, ["sensor"]),
            optional_entity(CONF_EV_CONNECTION_STATE, ["sensor"]),
            optional_entity(CONF_EV_CURRENT_LIMIT, ["number"]),
            optional_entity(CONF_EV_CURRENT_FEEDBACK, ["sensor", "number"]),
            optional_entity(CONF_EV_VOLTAGE, ["sensor"]),
            optional_entity(CONF_EV_PHASE_MODE, ["select", "sensor"]),
            optional_entity(CONF_EV_MODE, ["input_select", "select"]),
            optional_entity(CONF_EV_MANUAL_CURRENT, ["input_number", "number"]),
            optional_entity(CONF_EV_BATTERY_SOC, ["sensor"]),
            optional_entity(CONF_EV_BATTERY_MIN_SOC, ["input_number", "number"]),
            optional_entity(CONF_EV_BATTERY_TIME_TO_GO, ["sensor"]),
            optional_entity(CONF_EV_BATTERY_TARGET_TIME, ["input_datetime"]),
        ]
    )
    fields.update(
        {
            vol.Required(
                CONF_BATTERY_CHARGE_POSITIVE,
                default=current.get(
                    CONF_BATTERY_CHARGE_POSITIVE,
                    DEFAULT_BATTERY_CHARGE_POSITIVE,
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EV_PV_MODE,
                default=current.get(CONF_EV_PV_MODE, DEFAULT_EV_PV_MODE),
            ): selector.TextSelector(),
            vol.Required(
                CONF_EV_MANUAL_MODE,
                default=current.get(CONF_EV_MANUAL_MODE, DEFAULT_EV_MANUAL_MODE),
            ): selector.TextSelector(),
            vol.Required(
                CONF_EV_BATTERY_MODE,
                default=current.get(CONF_EV_BATTERY_MODE, DEFAULT_EV_BATTERY_MODE),
            ): selector.TextSelector(),
            vol.Required(
                CONF_EV_DISCONNECTED_STATE,
                default=current.get(
                    CONF_EV_DISCONNECTED_STATE, DEFAULT_EV_DISCONNECTED_STATE
                ),
            ): selector.TextSelector(),
            vol.Required(
                CONF_EV_PRIORITY,
                default=current.get(CONF_EV_PRIORITY, DEFAULT_EV_PRIORITY),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=5, unit_of_measurement="%"
                )
            ),
            vol.Required(
                CONF_EV_MAX_CURRENT,
                default=current.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=6, max=32, step=0.5, unit_of_measurement="A"
                )
            ),
            vol.Required(
                CONF_PV_SAFETY_MARGIN,
                default=current.get(CONF_PV_SAFETY_MARGIN, DEFAULT_PV_SAFETY_MARGIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=2000, step=50, unit_of_measurement="W"
                )
            ),
            vol.Required(
                CONF_ENABLE_EV_ACTUATION,
                default=current.get(
                    CONF_ENABLE_EV_ACTUATION, DEFAULT_ENABLE_EV_ACTUATION
                ),
            ): selector.BooleanSelector(),
        }
    )
    return vol.Schema(fields)


def _ev_options_errors(options: dict[str, Any]) -> dict[str, str]:
    """Validate relationships between EV options."""
    modes = {
        CONF_EV_PV_MODE: options.get(CONF_EV_PV_MODE),
        CONF_EV_MANUAL_MODE: options.get(CONF_EV_MANUAL_MODE),
        CONF_EV_BATTERY_MODE: options.get(CONF_EV_BATTERY_MODE),
    }
    values = [value for value in modes.values() if value is not None]
    if len(values) != len(set(values)):
        return {CONF_EV_BATTERY_MODE: "mode_values_must_differ"}
    return {}
