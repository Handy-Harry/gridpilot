"""GridPilot integration setup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import config_validation as cv

from .calculations import normalize_power
from .const import (
    CONF_AUTO_CHARGE_SOC_SOLAR,
    CONF_AUTO_CHARGE_SOC_SOLAR_EV,
    CONF_BATTERY_CHARGE_ENERGY,
    CONF_BATTERY_DISCHARGE_ENERGY,
    CONF_BATTERY_ENERGY,
    CONF_CHARGE_SOC,
    CONF_EV_CHARGE_ENERGY,
    CONF_EV_DEPARTURE_TIME,
    CONF_EV_OVERRIDE,
    CONF_EV_PHASE_MODE,
    CONF_GRID_POWER,
    CONF_GRIDPILOT_EV_MODE,
    CONF_HAS_EV,
    CONF_HAS_EV_CHARGER,
    CONF_HAS_GRID_CONNECTION,
    CONF_HAS_HOME_BATTERY,
    CONF_HAS_PV,
    CONF_HAS_SOC_LOADS,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    CONF_PRELOAD,
    CONF_SOC_LOAD_ENTITIES,
    CONF_SOC_LOAD_OFF_THRESHOLD,
    CONF_SOC_LOAD_ON_THRESHOLD,
    CONF_SOC_LOAD_THRESHOLDS,
    DEFAULT_AUTO_CHARGE_SOC_SOLAR,
    DEFAULT_AUTO_CHARGE_SOC_SOLAR_EV,
    DEFAULT_CHARGE_SOC,
    DEFAULT_EV_MODE,
    DEFAULT_PRELOAD,
    DEFAULT_SOC_LOAD_OFF_THRESHOLD,
    DEFAULT_SOC_LOAD_ON_THRESHOLD,
    VERSION,
)
from .const import DOMAIN as DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

FRONTEND_PATH = Path(__file__).parent / "frontend"
BRAND_PATH = Path(__file__).parent / "brand"
FRONTEND_URL = f"/gridpilot_static/gridpilot-card.js?v={VERSION}"
DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .runtime import GridPilotConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled frontend once."""
    return await _async_setup_frontend(hass)


async def _async_setup_frontend(hass: HomeAssistant) -> bool:
    """Serve and announce the card module for new and existing frontend sessions."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    if not hass.data.get(DATA_FRONTEND_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig("/gridpilot_static", str(FRONTEND_PATH), False),
                StaticPathConfig("/gridpilot_brand", str(BRAND_PATH), False),
            ]
        )
        hass.data[DATA_FRONTEND_REGISTERED] = True

    add_extra_js_url(hass, FRONTEND_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Set up GridPilot from a config entry."""
    from homeassistant.const import Platform

    from .controller import GridPilotController
    from .dashboard import async_ensure_dashboard
    from .runtime import GridPilotRuntime

    await _async_setup_frontend(hass)
    platforms = [
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SWITCH,
        Platform.TIME,
    ]
    controller = GridPilotController(hass, entry)
    entry.runtime_data = GridPilotRuntime(controller=controller)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    await controller.async_start()
    await async_ensure_dashboard(hass, entry)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Migrate legacy control parameters and SOC thresholds."""
    if entry.version > 19:
        return False

    data = dict(entry.data)
    options = dict(entry.options)
    version = entry.version

    if entry.version == 1:
        legacy_max_grid_power = data.get(CONF_MAX_GRID_POWER)

        if CONF_MAX_GRID_POWER not in options:
            migrated_max_grid_power = _legacy_max_grid_power(
                hass, legacy_max_grid_power
            )
            if migrated_max_grid_power is not None:
                options[CONF_MAX_GRID_POWER] = migrated_max_grid_power
                data.pop(CONF_MAX_GRID_POWER, None)
        else:
            data.pop(CONF_MAX_GRID_POWER, None)

        defaults = {CONF_CHARGE_SOC: DEFAULT_CHARGE_SOC}
        defaults.update(
            {
                CONF_AUTO_CHARGE_SOC_SOLAR: DEFAULT_AUTO_CHARGE_SOC_SOLAR,
                CONF_AUTO_CHARGE_SOC_SOLAR_EV: DEFAULT_AUTO_CHARGE_SOC_SOLAR_EV,
            }
        )
        for key, value in defaults.items():
            options.setdefault(key, value)

        version = 2

    if version == 2:
        options.setdefault(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC)
        options.pop(CONF_MINIMUM_SOC, None)
        options.pop(CONF_NORMAL_SOC, None)
        version = 3

    if version == 3:
        version = 4

    if version == 4:
        version = 5

    if version == 5:
        options.pop(CONF_EV_OVERRIDE, None)
        version = 6

    if version == 6:
        version = 7

    if version == 7:
        options.pop("minimum_charge_power", None)
        version = 8

    if version == 8:
        for key in (
            "ev_pv_mode",
            "ev_manual_mode",
            "ev_battery_mode",
            "ev_disconnected_state",
        ):
            options.pop(key, None)
        version = 9

    if version == 9:
        options.pop("ev_mode", None)
        options.setdefault(CONF_GRIDPILOT_EV_MODE, DEFAULT_EV_MODE)
        version = 10

    if version == 10:
        if options.get(CONF_EV_PHASE_MODE) == "sensor.alfen_charging_mode":
            options[CONF_EV_PHASE_MODE] = "select.alfen_usable_phases1"
        version = 11

    if version == 11:
        version = 12

    if version == 12:
        options.pop(CONF_EV_DEPARTURE_TIME, None)
        version = 13

    if version == 13:
        if data.get("profile") == "victron":
            options.setdefault(
                CONF_BATTERY_ENERGY, "sensor.batterij_resterende_energie"
            )
            options.setdefault(
                CONF_BATTERY_CHARGE_ENERGY,
                "sensor.gx_device_dc_battery_charge_energy",
            )
            options.setdefault(
                CONF_BATTERY_DISCHARGE_ENERGY,
                "sensor.gx_device_dc_battery_discharge_energy",
            )
            options.setdefault(
                CONF_EV_CHARGE_ENERGY, "sensor.alfen_real_energy_delivered_sum"
            )
        version = 14

    if version == 14:
        options.setdefault(CONF_BATTERY_ENERGY, "sensor.batterij_resterende_energie")
        options.setdefault(
            CONF_BATTERY_CHARGE_ENERGY,
            "sensor.gx_device_dc_battery_charge_energy",
        )
        options.setdefault(
            CONF_BATTERY_DISCHARGE_ENERGY,
            "sensor.gx_device_dc_battery_discharge_energy",
        )
        options.setdefault(
            CONF_EV_CHARGE_ENERGY, "sensor.alfen_real_energy_delivered_sum"
        )
        version = 15

    if version == 15:
        options.setdefault(CONF_BATTERY_ENERGY, "sensor.batterij_resterende_energie")
        options.setdefault(
            CONF_BATTERY_CHARGE_ENERGY,
            "sensor.gx_device_dc_battery_charge_energy",
        )
        options.setdefault(
            CONF_BATTERY_DISCHARGE_ENERGY,
            "sensor.gx_device_dc_battery_discharge_energy",
        )
        options.setdefault(
            CONF_EV_CHARGE_ENERGY, "sensor.alfen_real_energy_delivered_sum"
        )
        version = 16

    if version == 16:
        data.setdefault(CONF_HAS_GRID_CONNECTION, True)
        data.setdefault(CONF_HAS_HOME_BATTERY, True)
        data.setdefault(CONF_HAS_PV, CONF_GRID_POWER in options)
        data.setdefault(
            CONF_HAS_EV,
            any(
                key in options
                for key in (CONF_EV_CHARGE_ENERGY, "ev_vehicle_soc", "ev_current_limit")
            ),
        )
        data.setdefault(CONF_HAS_EV_CHARGER, "ev_current_limit" in options)
        data.setdefault(CONF_HAS_SOC_LOADS, "soc_load_entities" in options)
        version = 17

    if version == 17:
        entities = options.get(CONF_SOC_LOAD_ENTITIES, [])
        if isinstance(entities, list):
            on_threshold = options.pop(
                CONF_SOC_LOAD_ON_THRESHOLD, DEFAULT_SOC_LOAD_ON_THRESHOLD
            )
            off_threshold = options.pop(
                CONF_SOC_LOAD_OFF_THRESHOLD, DEFAULT_SOC_LOAD_OFF_THRESHOLD
            )
            options.setdefault(
                CONF_SOC_LOAD_THRESHOLDS,
                {
                    entity_id: {
                        "on": str(int(float(on_threshold))),
                        "off": str(int(float(off_threshold))),
                    }
                    for entity_id in entities
                    if isinstance(entity_id, str)
                },
            )
        version = 18

    if version == 18:
        options[CONF_PRELOAD] = bool(
            options.pop(CONF_AUTO_CHARGE_SOC_SOLAR, False)
            or options.pop(CONF_AUTO_CHARGE_SOC_SOLAR_EV, False)
        )
        options.setdefault(CONF_PRELOAD, DEFAULT_PRELOAD)
        version = 19

    if version != entry.version or data != entry.data or options != entry.options:
        hass.config_entries.async_update_entry(
            entry, data=data, options=options, version=version, minor_version=0
        )

    return True


def _legacy_max_grid_power(hass: HomeAssistant, value: Any) -> float | None:
    """Convert a legacy entity mapping or numeric value to persistent watts."""
    if isinstance(value, int | float):
        return max(0.0, float(value))
    if isinstance(value, str) and (state := hass.states.get(value)) is not None:
        try:
            return max(
                0.0,
                normalize_power(
                    float(state.state), state.attributes.get("unit_of_measurement")
                ),
            )
        except (TypeError, ValueError):
            pass
    return None


async def async_unload_entry(hass: HomeAssistant, entry: GridPilotConfigEntry) -> bool:
    """Unload GridPilot."""
    from homeassistant.const import Platform

    if not await entry.runtime_data.controller.async_shutdown():
        return False
    return await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.SENSOR,
            Platform.BINARY_SENSOR,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SWITCH,
            Platform.TIME,
        ],
    )


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry[Any]) -> None:
    """Reload after options change."""
    if entry.runtime_data.controller.consume_options_reload_skip():
        return
    await hass.config_entries.async_reload(entry.entry_id)
