"""Tests for GridPilot's bundled dashboard."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.gridpilot.const import (
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_MODE,
    CONF_EV_PHASE_MODE,
    CONF_EV_PRIORITY,
    CONF_EV_VEHICLE_SOC,
    CONF_GRID_SETPOINT,
)
from custom_components.gridpilot.dashboard import (
    DASHBOARD_URL,
    _dashboard_config,
    async_ensure_dashboard,
)


def _entry(options: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry-id",
        data={
            CONF_BATTERY_SOC: "sensor.battery_soc",
            CONF_BATTERY_POWER: "sensor.battery_power",
            CONF_GRID_SETPOINT: "number.grid_setpoint",
        },
        options=options or {},
    )


async def test_existing_dashboard_is_refreshed() -> None:
    """Refresh the installation-managed dashboard during setup."""
    hass = MagicMock(spec=HomeAssistant)
    dashboard = MagicMock()
    dashboard.async_save = AsyncMock()
    hass.data = {
        "lovelace": SimpleNamespace(dashboards={DASHBOARD_URL: dashboard})
    }

    with (
        patch(
            "custom_components.gridpilot.dashboard.DashboardsCollection"
        ) as collection,
        patch(
            "custom_components.gridpilot.dashboard.er.async_get"
        ) as entity_registry,
    ):
        entity_registry.return_value.async_get_entity_id.return_value = None
        await async_ensure_dashboard(hass, _entry())

    collection.assert_not_called()
    dashboard.async_save.assert_awaited_once()


async def test_dashboard_is_created_once() -> None:
    """Create and populate a missing storage dashboard."""
    hass = MagicMock(spec=HomeAssistant)
    lovelace = SimpleNamespace(dashboards={})
    hass.data = {"lovelace": lovelace}
    collection = MagicMock()
    collection.async_load = AsyncMock()
    collection.async_items.return_value = []
    collection.async_create_item = AsyncMock(
        return_value={"id": DASHBOARD_URL, "url_path": DASHBOARD_URL}
    )
    dashboard = MagicMock()
    dashboard.async_save = AsyncMock()

    with (
        patch(
            "custom_components.gridpilot.dashboard.DashboardsCollection",
            return_value=collection,
        ),
        patch(
            "custom_components.gridpilot.dashboard.LovelaceStorage",
            return_value=dashboard,
        ),
        patch(
            "custom_components.gridpilot.dashboard.frontend.async_register_built_in_panel"
        ) as register_panel,
        patch(
            "custom_components.gridpilot.dashboard.er.async_get"
        ) as entity_registry,
    ):
        entity_registry.return_value.async_get_entity_id.return_value = None
        await async_ensure_dashboard(hass, _entry())

    collection.async_create_item.assert_awaited_once()
    dashboard.async_save.assert_awaited_once()
    register_panel.assert_called_once()
    assert lovelace.dashboards[DASHBOARD_URL] is dashboard


def test_dashboard_uses_configured_entities() -> None:
    """Build generic cards from config-entry mappings, not local GPT helpers."""
    hass = MagicMock(spec=HomeAssistant)
    with patch("custom_components.gridpilot.dashboard.er.async_get") as registry:
        registry.return_value.async_get_entity_id.return_value = None
        config = _dashboard_config(
            hass,
            _entry(
                {
                    CONF_EV_MODE: "input_select.charge_mode",
                    CONF_EV_VEHICLE_SOC: "sensor.ev_soc",
                    CONF_EV_BATTERY_MIN_SOC: "input_number.minimum_soc",
                    CONF_CHARGE_SOC: 15,
                    CONF_EV_CURRENT_LIMIT: "number.ev_current",
                    CONF_EV_MANUAL_CURRENT: "input_number.manual_current",
                    CONF_EV_PHASE_MODE: "select.ev_phases",
                    CONF_EV_PRIORITY: 65,
                }
            ),
        )

    rendered = str(config)
    assert "sensor.battery_soc" in rendered
    assert "power_charge_positive" in rendered
    battery_card = config["views"][0]["sections"][0]["cards"][1]
    assert battery_card["minimum_soc"] == 10
    assert battery_card["charge_below"] == 15
    assert battery_card["normal_above"] == 20
    assert "number.grid_setpoint" in rendered
    assert "input_select.charge_mode" in rendered
    assert "sensor.ev_soc" in rendered
    assert "number.ev_current" in rendered
    assert "number.gridpilot_ev_priority" in rendered
    assert "input_number.manual_current" in rendered
    assert "select.ev_phases" in rendered
    assert "input_number.minimum_soc" in rendered
    assert "Thuisbatterij ontladen tot" in rendered
    ev_cards = config["views"][0]["sections"][1]["cards"]
    assert ev_cards[0]["heading"] == "EV laden"
    assert ev_cards[1]["type"] == "custom:gridpilot-card"
    assert ev_cards[1]["name"] == "EV-batterij"
    assert "PV-prioriteit: thuisbatterij 0% / EV 100%" in rendered
    assert "gpt_" not in rendered
    assert "thuisbatterij_naar_auto" not in rendered
