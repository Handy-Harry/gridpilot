"""Shared GridPilot test fixtures."""

from contextlib import suppress
from importlib.util import find_spec

import pytest

pytest_plugins = (
    ["pytest_homeassistant_custom_component.plugins"]
    if find_spec("pytest_homeassistant_custom_component")
    else []
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request: pytest.FixtureRequest):
    """Enable custom integrations in Home Assistant tests."""
    with suppress(pytest.FixtureLookupError):
        request.getfixturevalue("enable_custom_integrations")
    yield
