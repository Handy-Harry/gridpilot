"""Tests for GridPilot config-entry migrations."""

from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gridpilot import async_migrate_entry
from custom_components.gridpilot.const import (
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    DOMAIN,
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
    assert entry.version == 3
    assert CONF_MAX_GRID_POWER not in entry.data
    assert entry.options == {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 15,
        CONF_MINIMUM_CHARGE_POWER: 300,
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
    assert entry.version == 3
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
            CONF_MINIMUM_CHARGE_POWER: 300,
            CONF_ENABLE_ACTUATION: True,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 3
    assert entry.options == {
        CONF_MAX_GRID_POWER: 2900,
        CONF_CHARGE_SOC: 17,
        CONF_MINIMUM_CHARGE_POWER: 300,
        CONF_ENABLE_ACTUATION: True,
    }
