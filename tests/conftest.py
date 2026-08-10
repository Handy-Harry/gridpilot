"""Shared GridPilot test fixtures."""

from contextlib import suppress

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request: pytest.FixtureRequest):
    """Enable custom integrations in Home Assistant tests."""
    with suppress(pytest.FixtureLookupError):
        request.getfixturevalue("enable_custom_integrations")
    yield
