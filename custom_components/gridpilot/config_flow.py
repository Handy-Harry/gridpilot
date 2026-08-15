"""Config and options flows for GridPilot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_ENERGY,
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_DISCHARGE_ENERGY,
    CONF_BATTERY_ENERGY,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_ENABLE_EV_ACTUATION,
    CONF_ENABLE_SOC_LOAD_ACTUATION,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_SOC,
    CONF_EV_BATTERY_TARGET_TIME,
    CONF_EV_BATTERY_TIME_TO_GO,
    CONF_EV_CHARGE_ENERGY,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_DISCHARGE_ENERGY,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_MAX_CURRENT,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_PRIORITY,
    CONF_EV_VEHICLE_SOC,
    CONF_EV_VOLTAGE,
    CONF_GRID_POWER,
    CONF_GRID_SETPOINT,
    CONF_HAS_EV,
    CONF_HAS_EV_CHARGER,
    CONF_HAS_GRID_CONNECTION,
    CONF_HAS_HOME_BATTERY,
    CONF_HAS_PV,
    CONF_HAS_SOC_LOADS,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_PROFILE,
    CONF_PV_SAFETY_MARGIN,
    CONF_SOC_LOAD_ENTITIES,
    CONF_SOC_LOAD_OFF_THRESHOLD,
    CONF_SOC_LOAD_ON_THRESHOLD,
    CONF_SOC_LOAD_THRESHOLDS,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_CHARGE_SOC,
    DEFAULT_ENABLE_ACTUATION,
    DEFAULT_ENABLE_EV_ACTUATION,
    DEFAULT_ENABLE_SOC_LOAD_ACTUATION,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_PRIORITY,
    DEFAULT_MAX_GRID_POWER,
    DEFAULT_PV_SAFETY_MARGIN,
    DEFAULT_SOC_LOAD_OFF_THRESHOLD,
    DEFAULT_SOC_LOAD_ON_THRESHOLD,
    DOMAIN,
    PROFILE_GENERIC,
    PROFILE_VICTRON,
    SOC_LOAD_DOMAINS,
    SOC_LOAD_THRESHOLD_NEVER,
)

CONF_ADD_ANOTHER_SOC_LOAD = "add_another_soc_load"
CONF_REMOVE_SOC_LOAD = "remove_soc_load"
CONF_SOC_LOAD_ENTITY = "soc_load_entity"


def _entity_selector(domains: list[str]) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            filter=selector.EntityFilterSelectorConfig(domain=domains)
        )
    )


def _multiple_entity_selector(domains: list[str]) -> selector.EntitySelector:
    """Build an entity selector that accepts multiple flexible loads."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            multiple=True,
            filter=selector.EntityFilterSelectorConfig(domain=domains),
        )
    )


class GridPilotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the GridPilot setup flow."""

    VERSION = 18
    MINOR_VERSION = 0

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._completed_entity_steps: set[str] = set()
        self._reconfigure_entry: config_entries.ConfigEntry | None = None
        self._soc_load_entities: list[str] = []
        self._soc_load_pending: list[str] = []
        self._soc_load_thresholds: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the equipment that GridPilot should configure."""
        if user_input is not None:
            errors = _equipment_errors(user_input)
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_equipment_schema(),
                    errors=errors,
                )
            await self.async_set_unique_id("home")
            self._abort_if_unique_id_configured()
            self._data.update(user_input)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="user",
            data_schema=_equipment_schema(),
            last_step=False,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an existing GridPilot entry with the setup wizard."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            errors = _equipment_errors(user_input)
            if errors:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=_equipment_schema(entry.data),
                    errors=errors,
                )
            self._reconfigure_entry = entry
            self._data = {**entry.data, **user_input}
            self._options = dict(entry.options)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_equipment_schema(entry.data),
            last_step=False,
        )

    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the battery entities."""
        if user_input is not None:
            self._data.update(user_input)
            self._completed_entity_steps.add("battery")
            return await self._async_next_entity_step()

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
            last_step=False,
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
                grid_power = user_input.pop(CONF_GRID_POWER, None)
                self._data.update(user_input)
                if grid_power:
                    self._options[CONF_GRID_POWER] = grid_power
                return await self._async_next_entity_step()

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
        grid_power_key = (
            vol.Required(
                CONF_GRID_POWER,
                default=self._options.get(CONF_GRID_POWER, vol.UNDEFINED),
            )
            if self._data.get(CONF_HAS_PV)
            else vol.Optional(
                CONF_GRID_POWER,
                description={
                    "suggested_value": self._options.get(CONF_GRID_POWER)
                },
            )
        )
        schema = vol.Schema(
            {
                setpoint_key: _entity_selector(["number"]),
                grid_power_key: _entity_selector(["sensor"]),
                vol.Optional(CONF_HOME_LOAD): _entity_selector(["sensor"]),
                l1_key: _entity_selector(["sensor"]),
                l2_key: _entity_selector(["sensor"]),
                l3_key: _entity_selector(["sensor"]),
            }
        )
        return self.async_show_form(
            step_id="energy",
            data_schema=schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_pv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the grid-power mapping used for PV-surplus calculations."""
        if user_input is not None:
            self._options.update(user_input)
            self._completed_entity_steps.add("pv")
            return await self._async_next_entity_step()

        return self.async_show_form(
            step_id="pv",
            data_schema=_pv_entity_schema(self._options),
            last_step=False,
        )

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect optional electric-vehicle measurement mappings."""
        if user_input is not None:
            self._options.update(user_input)
            self._completed_entity_steps.add("vehicle")
            return await self._async_next_entity_step()

        return self.async_show_form(
            step_id="vehicle",
            data_schema=_vehicle_entity_schema(self._options),
            last_step=False,
        )

    async def async_step_charger(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect electric-vehicle charger entity mappings."""
        if user_input is not None:
            self._options.update(user_input)
            self._completed_entity_steps.add("charger")
            return await self._async_next_entity_step()

        return self.async_show_form(
            step_id="charger",
            data_schema=_charger_entity_schema(self._options),
            last_step=False,
        )

    async def async_step_soc_loads(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the guided configuration of SOC-controlled devices."""
        self._start_soc_load_flow()
        return await self.async_step_soc_load_device()

    async def async_step_soc_load_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure one SOC-controlled device and its thresholds."""
        existing_entity = self._soc_load_pending[0] if self._soc_load_pending else None
        if user_input is not None:
            entity_id = user_input[CONF_SOC_LOAD_ENTITY]
            if existing_entity is not None:
                self._soc_load_pending.pop(0)
                self._soc_load_thresholds.pop(existing_entity, None)

            if not user_input.get(CONF_REMOVE_SOC_LOAD, False):
                if entity_id not in self._soc_load_entities:
                    self._soc_load_entities.append(entity_id)
                self._soc_load_thresholds[entity_id] = {
                    "on": user_input[CONF_SOC_LOAD_ON_THRESHOLD],
                    "off": user_input[CONF_SOC_LOAD_OFF_THRESHOLD],
                }

            if self._soc_load_pending:
                return await self.async_step_soc_load_device()
            return await self.async_step_soc_load_add()

        return self.async_show_form(
            step_id="soc_load_device",
            data_schema=_soc_load_device_schema(
                existing_entity, self._soc_load_thresholds, existing_entity is not None
            ),
            last_step=False,
        )

    async def async_step_soc_load_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add another SOC-controlled device or continue configuration."""
        if user_input is not None:
            if user_input[CONF_ADD_ANOTHER_SOC_LOAD]:
                return await self.async_step_soc_load_device()

            self._options[CONF_SOC_LOAD_ENTITIES] = self._soc_load_entities
            self._options[CONF_SOC_LOAD_THRESHOLDS] = self._soc_load_thresholds
            self._completed_entity_steps.add("soc_loads")
            return await self._async_next_entity_step()

        return self.async_show_form(
            step_id="soc_load_add",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADD_ANOTHER_SOC_LOAD, default=False): (
                        selector.BooleanSelector()
                    )
                }
            ),
            last_step=False,
        )

    def _start_soc_load_flow(self) -> None:
        """Load the configured devices into the guided SOC-load flow once."""
        if hasattr(self, "_soc_load_started"):
            return
        self._soc_load_started = True
        entities = self._options.get(CONF_SOC_LOAD_ENTITIES, [])
        self._soc_load_pending = list(entities) if isinstance(entities, list) else []
        thresholds = self._options.get(CONF_SOC_LOAD_THRESHOLDS, {})
        self._soc_load_thresholds = (
            dict(thresholds) if isinstance(thresholds, dict) else {}
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect GridPilot-specific operating settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _soc_load_options_errors(user_input)
            if not errors:
                self._options.update(user_input)
                if self._reconfigure_entry is not None:
                    self.hass.config_entries.async_update_entry(
                        self._reconfigure_entry,
                        data=self._data,
                        options=self._options,
                    )
                    return self.async_abort(reason="reconfigure_successful")
                return self.async_create_entry(
                    title="GridPilot", data=self._data, options=self._options
                )

        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(self._data, self._options),
            errors=errors,
            last_step=True,
        )

    async def _async_next_entity_step(self) -> ConfigFlowResult:
        """Advance to the next screen selected on the equipment screen."""
        if "battery" not in self._completed_entity_steps:
            return await self.async_step_battery()
        if (
            self._data.get(CONF_HAS_EV)
            and "vehicle" not in self._completed_entity_steps
        ):
            return await self.async_step_vehicle()
        if (
            self._data.get(CONF_HAS_EV_CHARGER)
            and "charger" not in self._completed_entity_steps
        ):
            return await self.async_step_charger()
        if (
            self._data.get(CONF_HAS_SOC_LOADS)
            and "soc_loads" not in self._completed_entity_steps
        ):
            return await self.async_step_soc_loads()
        return await self.async_step_settings()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GridPilotOptionsFlow:
        """Return the options flow."""
        return GridPilotOptionsFlow()


class GridPilotOptionsFlow(config_entries.OptionsFlow):
    """Reconfigure GridPilot through the integration's Configure button."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._completed_entity_steps: set[str] = set()
        self._soc_load_entities: list[str] = []
        self._soc_load_pending: list[str] = []
        self._soc_load_thresholds: dict[str, dict[str, Any]] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select installed equipment before editing its entity mappings."""
        if user_input is not None:
            errors = _equipment_errors(user_input)
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_equipment_schema(self.config_entry.data),
                    errors=errors,
                )
            self._data = {**self.config_entry.data, **user_input}
            self._options = dict(self.config_entry.options)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="init",
            data_schema=_equipment_schema(self.config_entry.data),
            last_step=False,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save the entity mappings and GridPilot-specific settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _soc_load_options_errors(user_input)
            if not errors:
                self._options.update(user_input)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=self._data,
                )
                return self.async_create_entry(title="", data=self._options)

        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(self._data, self._options),
            errors=errors,
            last_step=True,
        )

    async_step_battery = GridPilotConfigFlow.async_step_battery
    async_step_energy = GridPilotConfigFlow.async_step_energy
    async_step_vehicle = GridPilotConfigFlow.async_step_vehicle
    async_step_charger = GridPilotConfigFlow.async_step_charger
    async_step_soc_loads = GridPilotConfigFlow.async_step_soc_loads
    async_step_soc_load_device = GridPilotConfigFlow.async_step_soc_load_device
    async_step_soc_load_add = GridPilotConfigFlow.async_step_soc_load_add
    _start_soc_load_flow = GridPilotConfigFlow._start_soc_load_flow
    _async_next_entity_step = GridPilotConfigFlow._async_next_entity_step


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
                CONF_ENABLE_ACTUATION,
                default=current.get(CONF_ENABLE_ACTUATION, DEFAULT_ENABLE_ACTUATION),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ENABLE_SOC_LOAD_ACTUATION,
                default=current.get(
                    CONF_ENABLE_SOC_LOAD_ACTUATION,
                    DEFAULT_ENABLE_SOC_LOAD_ACTUATION,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_SOC_LOAD_ENTITIES,
                description={
                    "suggested_value": current.get(CONF_SOC_LOAD_ENTITIES, [])
                },
            ): _multiple_entity_selector(sorted(SOC_LOAD_DOMAINS)),
        }
    )


def _equipment_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    """Build the initial equipment-selection screen."""
    current = current or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HAS_GRID_CONNECTION,
                default=current.get(CONF_HAS_GRID_CONNECTION, True),
            ): (
                selector.BooleanSelector()
            ),
            vol.Required(
                CONF_HAS_PV, default=current.get(CONF_HAS_PV, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_HAS_HOME_BATTERY,
                default=current.get(CONF_HAS_HOME_BATTERY, True),
            ): (
                selector.BooleanSelector()
            ),
            vol.Required(
                CONF_HAS_EV, default=current.get(CONF_HAS_EV, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_HAS_EV_CHARGER,
                default=current.get(CONF_HAS_EV_CHARGER, False),
            ): (
                selector.BooleanSelector()
            ),
            vol.Required(
                CONF_HAS_SOC_LOADS,
                default=current.get(CONF_HAS_SOC_LOADS, False),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_PROFILE,
                default=current.get(CONF_PROFILE, PROFILE_GENERIC),
            ): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[PROFILE_GENERIC, PROFILE_VICTRON],
                        translation_key="profile",
                    )
                )
            ),
        }
    )


def _pv_entity_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the PV-surplus measurement schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_GRID_POWER,
                default=current.get(CONF_GRID_POWER, vol.UNDEFINED),
            ): _entity_selector(["sensor"])
        }
    )


def _vehicle_entity_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the optional electric-vehicle measurement schema."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_EV_VEHICLE_SOC,
                description={"suggested_value": current.get(CONF_EV_VEHICLE_SOC)},
            ): _entity_selector(["sensor"]),
            vol.Optional(
                CONF_EV_CHARGE_ENERGY,
                description={"suggested_value": current.get(CONF_EV_CHARGE_ENERGY)},
            ): _entity_selector(["sensor"]),
            vol.Optional(
                CONF_EV_DISCHARGE_ENERGY,
                description={"suggested_value": current.get(CONF_EV_DISCHARGE_ENERGY)},
            ): _entity_selector(["sensor"]),
        }
    )


def _charger_entity_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the electric-vehicle charger entity schema."""
    fields = _ev_options_schema(current).schema.copy()
    for key in (
        CONF_GRID_POWER,
        CONF_EV_VEHICLE_SOC,
        CONF_EV_CHARGE_ENERGY,
        CONF_EV_DISCHARGE_ENERGY,
    ):
        fields.pop(next(marker for marker in fields if marker.schema == key))
    for key in (
        CONF_ENABLE_EV_ACTUATION,
        CONF_BATTERY_CHARGE_POSITIVE,
        CONF_EV_PRIORITY,
        CONF_EV_MAX_CURRENT,
        CONF_PV_SAFETY_MARGIN,
    ):
        fields.pop(next(marker for marker in fields if marker.schema == key))
    return vol.Schema(fields)


def _soc_load_device_schema(
    entity_id: str | None,
    thresholds: dict[str, dict[str, Any]],
    can_remove: bool,
) -> vol.Schema:
    """Build one standard form for a device and its switching thresholds."""
    options = [
        {"label": "Nooit", "value": SOC_LOAD_THRESHOLD_NEVER},
        *(
            {"label": f"{value}%", "value": str(value)}
            for value in range(0, 101, 10)
        ),
    ]
    device_thresholds = thresholds.get(entity_id, {}) if entity_id else {}
    device_thresholds = (
        device_thresholds if isinstance(device_thresholds, dict) else {}
    )
    entity_field = (
        vol.Required(CONF_SOC_LOAD_ENTITY, default=entity_id)
        if entity_id
        else vol.Required(CONF_SOC_LOAD_ENTITY)
    )
    fields: dict[Any, Any] = {
        entity_field: _entity_selector(sorted(SOC_LOAD_DOMAINS)),
        vol.Required(
            CONF_SOC_LOAD_ON_THRESHOLD,
            default=_soc_threshold_option(
                device_thresholds.get("on", DEFAULT_SOC_LOAD_ON_THRESHOLD)
            ),
        ): selector.SelectSelector(selector.SelectSelectorConfig(options=options)),
        vol.Required(
            CONF_SOC_LOAD_OFF_THRESHOLD,
            default=_soc_threshold_option(
                device_thresholds.get("off", DEFAULT_SOC_LOAD_OFF_THRESHOLD)
            ),
        ): selector.SelectSelector(selector.SelectSelectorConfig(options=options)),
    }
    if can_remove:
        fields[vol.Required(CONF_REMOVE_SOC_LOAD, default=False)] = (
            selector.BooleanSelector()
        )
    return vol.Schema(fields)


def _soc_threshold_option(value: Any) -> str:
    """Normalize migrated numeric thresholds for the string-based selector."""
    if value == SOC_LOAD_THRESHOLD_NEVER or value is None:
        return SOC_LOAD_THRESHOLD_NEVER
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return SOC_LOAD_THRESHOLD_NEVER


def _settings_schema(data: dict[str, Any], current: dict[str, Any]) -> vol.Schema:
    """Build GridPilot's settings screen for the selected equipment."""
    fields = _control_options_schema(current).schema.copy()
    fields.pop(
        next(marker for marker in fields if marker.schema == CONF_SOC_LOAD_ENTITIES)
    )
    if not data.get(CONF_HAS_SOC_LOADS):
        for key in (CONF_ENABLE_SOC_LOAD_ACTUATION,):
            fields.pop(next(marker for marker in fields if marker.schema == key))
    if data.get(CONF_HAS_EV_CHARGER):
        ev_fields = _ev_options_schema(current).schema
        for key in (
            CONF_ENABLE_EV_ACTUATION,
            CONF_BATTERY_CHARGE_POSITIVE,
            CONF_EV_PRIORITY,
            CONF_EV_MAX_CURRENT,
            CONF_PV_SAFETY_MARGIN,
        ):
            marker = next(marker for marker in ev_fields if marker.schema == key)
            fields[marker] = ev_fields[marker]
    return vol.Schema(fields)


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
            (
                vol.Required(
                    CONF_ENABLE_EV_ACTUATION,
                    default=current.get(
                        CONF_ENABLE_EV_ACTUATION, DEFAULT_ENABLE_EV_ACTUATION
                    ),
                ),
                selector.BooleanSelector(),
            ),
            optional_entity(CONF_GRID_POWER, ["sensor"]),
            optional_entity(CONF_EV_POWER, ["sensor"]),
            optional_entity(CONF_EV_VEHICLE_SOC, ["sensor"]),
            optional_entity(CONF_EV_CONNECTION_STATE, ["sensor"]),
            optional_entity(CONF_EV_CURRENT_LIMIT, ["number"]),
            optional_entity(CONF_EV_CURRENT_FEEDBACK, ["sensor", "number"]),
            optional_entity(CONF_EV_VOLTAGE, ["sensor"]),
            optional_entity(CONF_EV_PHASE_MODE, ["select", "sensor"]),
            optional_entity(CONF_EV_MANUAL_CURRENT, ["input_number", "number"]),
            optional_entity(CONF_EV_BATTERY_SOC, ["sensor"]),
            optional_entity(CONF_EV_BATTERY_MIN_SOC, ["input_number", "number"]),
            optional_entity(CONF_EV_BATTERY_TIME_TO_GO, ["sensor"]),
            optional_entity(CONF_EV_BATTERY_TARGET_TIME, ["input_datetime"]),
            optional_entity(CONF_BATTERY_ENERGY, ["sensor"]),
            optional_entity(CONF_BATTERY_CHARGE_ENERGY, ["sensor"]),
            optional_entity(CONF_BATTERY_DISCHARGE_ENERGY, ["sensor"]),
            optional_entity(CONF_EV_CHARGE_ENERGY, ["sensor"]),
            optional_entity(CONF_EV_DISCHARGE_ENERGY, ["sensor"]),
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
                    min=6, max=32, step=0.1, unit_of_measurement="A"
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
        }
    )
    return vol.Schema(fields)


def _ev_options_errors(options: dict[str, Any]) -> dict[str, str]:
    """Validate EV options."""
    return {}


def _soc_load_options_errors(options: dict[str, Any]) -> dict[str, str]:
    """Validate the remaining SOC-load options."""
    return {}


def _equipment_errors(equipment: dict[str, Any]) -> dict[str, str]:
    """Require the equipment needed by GridPilot's battery controller."""
    if not equipment[CONF_HAS_GRID_CONNECTION]:
        return {CONF_HAS_GRID_CONNECTION: "grid_connection_required"}
    if not equipment[CONF_HAS_HOME_BATTERY]:
        return {CONF_HAS_HOME_BATTERY: "home_battery_required"}
    return {}
