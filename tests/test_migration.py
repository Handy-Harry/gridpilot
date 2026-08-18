"""Tests for GridPilot config-entry migrations."""

from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gridpilot import async_migrate_entry
from custom_components.gridpilot.const import (
    CONF_AUTO_CHARGE_SOC_SOLAR,
    CONF_AUTO_CHARGE_SOC_SOLAR_EV,
    CONF_BATTERY_CHARGE_ENERGY,
    CONF_BATTERY_DISCHARGE_ENERGY,
    CONF_BATTERY_ENERGY,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_EV_CHARGE_ENERGY,
    CONF_GRIDPILOT_EV_MODE,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    CONF_PRELOAD,
    CONF_SOC_LOAD_ENTITIES,
    CONF_SOC_LOAD_OFF_THRESHOLD,
    CONF_SOC_LOAD_ON_THRESHOLD,
    CONF_SOC_LOAD_THRESHOLDS,
    DEFAULT_EV_MODE,
    DOMAIN,
    PROFILE_VICTRON,
)


async def test_migrate_grid_limit_entity_to_options(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "sensor.max_grid_power",
        "2.9",
        {"unit_of_measurement": UnitOfPower.KILO_WATT},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={CONF_MAX_GRID_POWER: "sensor.max_grid_power"},
        options={CONF_MINIMUM_SOC: 11},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert CONF_MAX_GRID_POWER not in entry.data
    assert entry.options == {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 15,
        CONF_PRELOAD: False,
        CONF_GRIDPILOT_EV_MODE: DEFAULT_EV_MODE,
        CONF_SOC_LOAD_THRESHOLDS: {},
        **_default_energy_meters(),
    }


async def test_migration_preserves_unavailable_grid_limit_entity(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={CONF_MAX_GRID_POWER: "sensor.unavailable_grid_limit"},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.data[CONF_MAX_GRID_POWER] == "sensor.unavailable_grid_limit"
    assert CONF_MAX_GRID_POWER not in entry.options


async def test_migrate_soc_curve_to_single_threshold(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        data={},
        options={
            CONF_MAX_GRID_POWER: 2900,
            CONF_MINIMUM_SOC: 12,
            CONF_CHARGE_SOC: 17,
            CONF_NORMAL_SOC: 22,
            CONF_ENABLE_ACTUATION: True,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.options == {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 17,
        CONF_ENABLE_ACTUATION: True,
        CONF_GRIDPILOT_EV_MODE: DEFAULT_EV_MODE,
        CONF_PRELOAD: False,
        CONF_SOC_LOAD_THRESHOLDS: {},
        **_default_energy_meters(),
    }


async def test_version_three_migration_preserves_all_options(
    hass: HomeAssistant,
) -> None:
    options = {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 17,
        CONF_ENABLE_ACTUATION: True,
        "grid_power": "sensor.grid_power",
        "enable_ev_actuation": False,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        minor_version=0,
        data={"battery_soc": "sensor.battery_soc"},
        options=options,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.options == {
        **options,
        CONF_GRIDPILOT_EV_MODE: DEFAULT_EV_MODE,
        CONF_PRELOAD: False,
        CONF_SOC_LOAD_THRESHOLDS: {},
        **_default_energy_meters(),
    }


async def test_version_four_migration_preserves_ev_options(
    hass: HomeAssistant,
) -> None:
    options = {
        CONF_MAX_GRID_POWER: 2900,
        "ev_mode": "input_select.laadmodus",
        "ev_override": "input_boolean.thuisbatterij_naar_auto",
        "enable_ev_actuation": False,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data={"battery_soc": "sensor.battery_soc"},
        options=options,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.options == {
        CONF_MAX_GRID_POWER: 2900,
        "enable_ev_actuation": False,
        CONF_GRIDPILOT_EV_MODE: DEFAULT_EV_MODE,
        CONF_PRELOAD: False,
        CONF_SOC_LOAD_THRESHOLDS: {},
        **_default_energy_meters(),
    }


async def test_victron_migration_configures_capacity_energy_meters(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=15,
        data={"profile": PROFILE_VICTRON},
        options={},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.options[CONF_BATTERY_ENERGY] == "sensor.batterij_resterende_energie"
    assert entry.options[CONF_BATTERY_CHARGE_ENERGY] == (
        "sensor.gx_device_dc_battery_charge_energy"
    )
    assert entry.options[CONF_BATTERY_DISCHARGE_ENERGY] == (
        "sensor.gx_device_dc_battery_discharge_energy"
    )
    assert entry.options[CONF_EV_CHARGE_ENERGY] == (
        "sensor.alfen_real_energy_delivered_sum"
    )


async def test_migrate_shared_soc_load_thresholds(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=17,
        data={},
        options={
            CONF_SOC_LOAD_ENTITIES: ["switch.flexible_load"],
            CONF_SOC_LOAD_ON_THRESHOLD: 90,
            CONF_SOC_LOAD_OFF_THRESHOLD: 30,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.options == {
        CONF_SOC_LOAD_ENTITIES: ["switch.flexible_load"],
        CONF_SOC_LOAD_THRESHOLDS: {
            "switch.flexible_load": {"on": "90", "off": "30"}
        },
        CONF_PRELOAD: False,
    }


async def test_migrate_auto_charge_modes_to_preload(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=18,
        data={},
        options={
            CONF_AUTO_CHARGE_SOC_SOLAR: False,
            CONF_AUTO_CHARGE_SOC_SOLAR_EV: True,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 19
    assert entry.options == {CONF_PRELOAD: True}


def _default_energy_meters() -> dict[str, str]:
    return {
        CONF_BATTERY_ENERGY: "sensor.batterij_resterende_energie",
        CONF_BATTERY_CHARGE_ENERGY: "sensor.gx_device_dc_battery_charge_energy",
        CONF_BATTERY_DISCHARGE_ENERGY: "sensor.gx_device_dc_battery_discharge_energy",
        CONF_EV_CHARGE_ENERGY: "sensor.alfen_real_energy_delivered_sum",
    }
