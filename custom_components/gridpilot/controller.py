"""Read-only GridPilot shadow controller."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .calculations import BatteryCurve, calculate_battery_decision, normalize_power
from .const import (
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    DEFAULT_CHARGE_SOC,
    DEFAULT_MAX_GRID_POWER,
    DEFAULT_MINIMUM_CHARGE_POWER,
    DEFAULT_MINIMUM_SOC,
    DEFAULT_NORMAL_SOC,
    MODE_UNAVAILABLE,
    UPDATE_INTERVAL,
)
from .models import ControlDecision
from .runtime import GridPilotConfigEntry

_LOGGER = logging.getLogger(__name__)


class GridPilotController:
    """Calculate decisions from existing Home Assistant entities."""

    def __init__(self, hass: HomeAssistant, entry: GridPilotConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.decision = ControlDecision(
            valid=False,
            mode=MODE_UNAVAILABLE,
            reason="GridPilot has not calculated a decision yet",
        )
        self._listeners: set[Callable[[], None]] = set()
        self._refresh_lock = asyncio.Lock()

    async def async_start(self) -> None:
        """Start state and interval tracking."""
        source_entities = {
            value
            for key, value in self.entry.data.items()
            if key
            in {
                CONF_BATTERY_SOC,
                CONF_HOME_LOAD,
                CONF_HOME_LOAD_L1,
                CONF_HOME_LOAD_L2,
                CONF_HOME_LOAD_L3,
                CONF_MAX_GRID_POWER,
            }
            and value
        }
        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                source_entities,
                self._async_state_changed,
            )
        )
        self.entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_periodic_refresh,
                UPDATE_INTERVAL,
            )
        )
        await self.async_refresh()

    async def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Refresh after a configured source changes."""
        await self.async_refresh()

    async def _async_periodic_refresh(self, now: datetime) -> None:
        """Refresh on the fallback interval."""
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Calculate and publish one new shadow decision."""
        async with self._refresh_lock:
            try:
                soc = self._numeric_state(self.entry.data[CONF_BATTERY_SOC])
                home_load = self._home_load()
                options = self.entry.options
                max_grid_power = self._max_grid_power()
                curve = BatteryCurve(
                    minimum_soc=float(
                        options.get(CONF_MINIMUM_SOC, DEFAULT_MINIMUM_SOC)
                    ),
                    charge_soc=float(options.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC)),
                    normal_soc=float(options.get(CONF_NORMAL_SOC, DEFAULT_NORMAL_SOC)),
                    minimum_charge_power=float(
                        options.get(
                            CONF_MINIMUM_CHARGE_POWER,
                            DEFAULT_MINIMUM_CHARGE_POWER,
                        )
                    ),
                )
                self.decision = calculate_battery_decision(
                    soc=soc,
                    home_load=home_load,
                    max_grid_power=max_grid_power,
                    curve=curve,
                )
            except (KeyError, TypeError, ValueError) as err:
                self.decision = ControlDecision(
                    valid=False,
                    mode=MODE_UNAVAILABLE,
                    reason=str(err),
                )
                _LOGGER.debug("Unable to calculate GridPilot decision: %s", err)

            for listener in tuple(self._listeners):
                listener()

    def _numeric_state(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Entity is unavailable: {entity_id}")
        value = float(state.state)
        if not value == value:
            raise ValueError(f"Entity is not numeric: {entity_id}")
        return value

    def _power_state(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Power entity is unavailable: {entity_id}")
        return normalize_power(
            float(state.state), state.attributes.get("unit_of_measurement")
        )

    def _home_load(self) -> float:
        if entity_id := self.entry.data.get(CONF_HOME_LOAD):
            return self._power_state(entity_id)
        phase_entities = [
            self.entry.data.get(CONF_HOME_LOAD_L1),
            self.entry.data.get(CONF_HOME_LOAD_L2),
            self.entry.data.get(CONF_HOME_LOAD_L3),
        ]
        if not all(phase_entities):
            raise ValueError("Configure a total home load or all three phase entities")
        return sum(self._power_state(entity_id) for entity_id in phase_entities)

    def _max_grid_power(self) -> float:
        """Return the internal limit or a legacy entity value during migration."""
        if CONF_MAX_GRID_POWER in self.entry.options:
            return float(self.entry.options[CONF_MAX_GRID_POWER])
        if entity_id := self.entry.data.get(CONF_MAX_GRID_POWER):
            return self._power_state(entity_id)
        return DEFAULT_MAX_GRID_POWER

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to decision updates."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @property
    def diagnostics(self) -> dict[str, object]:
        """Return bounded runtime diagnostics."""
        return {
            "decision": {
                "valid": self.decision.valid,
                "mode": self.decision.mode,
                "reason": self.decision.reason,
                "soc": self.decision.soc,
                "home_load": self.decision.home_load,
                "max_grid_power": self.decision.max_grid_power,
                "requested_grid_setpoint": self.decision.requested_grid_setpoint,
            },
            "shadow_mode": True,
        }
