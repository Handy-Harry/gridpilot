"""Tests for GridPilot's bundled dashboard card registration."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from custom_components.gridpilot import (
    DATA_FRONTEND_REGISTERED,
    FRONTEND_URL,
    async_setup,
)


async def test_frontend_resource_is_reannounced_on_setup(hass: HomeAssistant) -> None:
    """Register static paths once but announce the module for every setup call."""
    hass.http.async_register_static_paths = AsyncMock()

    with patch("homeassistant.components.frontend.add_extra_js_url") as add_resource:
        assert await async_setup(hass, {})
        assert await async_setup(hass, {})

    assert hass.data[DATA_FRONTEND_REGISTERED]
    hass.http.async_register_static_paths.assert_awaited_once()
    assert add_resource.call_args_list[0].args == (hass, FRONTEND_URL)
    assert add_resource.call_args_list[1].args == (hass, FRONTEND_URL)
