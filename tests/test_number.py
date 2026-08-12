"""Tests for GridPilot number entities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from custom_components.gridpilot.const import CONF_EV_PRIORITY, DEFAULT_EV_PRIORITY
from custom_components.gridpilot.number import EVPriorityNumber


def _entry(options: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry-id",
        options=options or {},
        runtime_data=SimpleNamespace(controller=MagicMock()),
    )


def test_ev_priority_uses_configured_value() -> None:
    """Expose the persisted PV share assigned to the EV."""
    assert EVPriorityNumber(_entry()).native_value == DEFAULT_EV_PRIORITY
    assert EVPriorityNumber(_entry({CONF_EV_PRIORITY: 75})).native_value == 75


async def test_ev_priority_updates_config_entry() -> None:
    """Persist dashboard slider changes in config-entry options."""
    entry = _entry({CONF_EV_PRIORITY: 50, "other": True})
    entity = EVPriorityNumber(entry)
    entity.hass = MagicMock()
    entity.controller.async_update_ev_priority = AsyncMock()

    await entity.async_set_native_value(80)

    entity.controller.async_update_ev_priority.assert_awaited_once_with(80)
