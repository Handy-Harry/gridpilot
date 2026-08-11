"""GridPilot battery controller."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from datetime import datetime
from time import monotonic

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .calculations import BatteryCurve, calculate_battery_decision, normalize_power
from .const import (
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_MINIMUM_SOC,
    CONF_NORMAL_SOC,
    DEFAULT_CHARGE_SOC,
    DEFAULT_ENABLE_ACTUATION,
    DEFAULT_MAX_GRID_POWER,
    DEFAULT_MINIMUM_CHARGE_POWER,
    DEFAULT_MINIMUM_SOC,
    DEFAULT_NORMAL_SOC,
    MIN_ACTUATION_INTERVAL,
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
        self._actuation_enabled = bool(
            entry.options.get(CONF_ENABLE_ACTUATION, DEFAULT_ENABLE_ACTUATION)
        )
        self.last_applied_setpoint: float | None = None
        self.last_actuation_error: str | None = None
        self._last_write_monotonic: float | None = None
        self._requires_neutralization = self._actuation_enabled

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
        """Calculate, optionally apply and publish one new decision."""
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

            await self._async_apply_decision()

            for listener in tuple(self._listeners):
                listener()

    async def _async_apply_decision(self) -> None:
        """Apply a valid decision or reset to the safe neutral setpoint."""
        if not self._actuation_enabled:
            if self._requires_neutralization:
                try:
                    await self._async_write_setpoint(0.0, force=True)
                except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
                    self.last_actuation_error = str(err)
                    _LOGGER.warning(
                        "Unable to retry GridPilot setpoint neutralization: %s", err
                    )
            else:
                self.last_actuation_error = None
            return

        requested = (
            self.decision.requested_grid_setpoint if self.decision.valid else 0.0
        )
        if requested is None:
            requested = 0.0

        try:
            await self._async_write_setpoint(requested, force=not self.decision.valid)
        except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
            self.last_actuation_error = str(err)
            _LOGGER.error("Unable to apply GridPilot setpoint: %s", err)

    async def _async_write_setpoint(
        self, requested: float, *, force: bool = False
    ) -> None:
        """Validate and write one grid setpoint through Home Assistant."""
        entity_id = self.entry.data[CONF_GRID_SETPOINT]
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Grid setpoint is unavailable: {entity_id}")

        unit = state.attributes.get("unit_of_measurement")
        if unit is None:
            raise ValueError(f"Grid setpoint has no power unit: {entity_id}")
        if "min" not in state.attributes or "max" not in state.attributes:
            raise ValueError(f"Grid setpoint has no numeric limits: {entity_id}")

        scale = normalize_power(1.0, unit)
        current = normalize_power(float(state.state), unit)
        minimum = normalize_power(float(state.attributes["min"]), unit)
        maximum = normalize_power(float(state.attributes["max"]), unit)
        if not minimum <= requested <= maximum:
            raise ValueError(
                f"Grid setpoint {requested} W is outside {minimum}..{maximum} W"
            )

        if math.isclose(current, requested, abs_tol=1.0):
            self.last_applied_setpoint = requested
            self.last_actuation_error = None
            self._requires_neutralization = not math.isclose(
                requested, 0.0, abs_tol=1.0
            )
            return

        now = monotonic()
        if (
            not force
            and self._last_write_monotonic is not None
            and now - self._last_write_monotonic
            < MIN_ACTUATION_INTERVAL.total_seconds()
        ):
            return

        await self.hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": requested / scale},
            blocking=True,
        )
        self.last_applied_setpoint = requested
        self.last_actuation_error = None
        self._last_write_monotonic = now
        self._requires_neutralization = not math.isclose(requested, 0.0, abs_tol=1.0)

    async def async_shutdown(self) -> bool:
        """Return an active actuator to its neutral setpoint before unloading."""
        async with self._refresh_lock:
            if not self._actuation_enabled and not self._requires_neutralization:
                return True
            try:
                await self._async_write_setpoint(0.0, force=True)
            except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
                self.last_actuation_error = str(err)
                self._actuation_enabled = False
                _LOGGER.warning(
                    "Unable to reset GridPilot setpoint during unload: %s", err
                )
                for listener in tuple(self._listeners):
                    listener()
                return False
            self._actuation_enabled = False
            return True

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
    def actuation_enabled(self) -> bool:
        """Return whether GridPilot is allowed to write the configured setpoint."""
        return self._actuation_enabled

    @property
    def actuation_healthy(self) -> bool:
        """Return whether active control has applied without an error."""
        return self.last_actuation_error is None

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
            "actuation": {
                "enabled": self.actuation_enabled,
                "healthy": self.actuation_healthy,
                "last_applied_setpoint": self.last_applied_setpoint,
                "last_error": self.last_actuation_error,
                "neutralization_pending": self._requires_neutralization,
            },
            "shadow_mode": not self.actuation_enabled,
        }
