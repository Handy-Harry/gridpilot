"""Typed config-entry runtime data for GridPilot."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .controller import GridPilotController


@dataclass(slots=True)
class GridPilotRuntime:
    """Runtime state attached to the config entry."""

    controller: "GridPilotController"


type GridPilotConfigEntry = ConfigEntry[GridPilotRuntime]
