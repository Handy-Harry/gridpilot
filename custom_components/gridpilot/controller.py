"""GridPilot battery controller."""

from __future__ import annotations

import asyncio
import logging
import math
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from statistics import median
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
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_ENABLE_EV_ACTUATION,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_DISCONNECTED_STATE,
    CONF_EV_MAX_CURRENT,
    CONF_EV_MODE,
    CONF_EV_OVERRIDE,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_PRIORITY,
    CONF_EV_PV_MODE,
    CONF_EV_VOLTAGE,
    CONF_GRID_POWER,
    CONF_GRID_SETPOINT,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_MINIMUM_CHARGE_POWER,
    CONF_PV_SAFETY_MARGIN,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_CHARGE_SOC,
    DEFAULT_ENABLE_ACTUATION,
    DEFAULT_ENABLE_EV_ACTUATION,
    DEFAULT_EV_DISCONNECTED_STATE,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_PRIORITY,
    DEFAULT_EV_PV_MODE,
    DEFAULT_MAX_GRID_POWER,
    DEFAULT_MINIMUM_CHARGE_POWER,
    DEFAULT_PV_SAFETY_MARGIN,
    EV_CURRENT_DEADBAND,
    EV_CURRENT_MEDIAN_WINDOW,
    EV_CURRENT_STEP,
    EV_MIN_CURRENT,
    EV_MODE_BLOCKED,
    EV_MODE_CHARGING,
    EV_MODE_DISCONNECTED,
    EV_MODE_INACTIVE,
    EV_MODE_RESTART_BLOCKED,
    EV_MODE_STOP_DELAY,
    EV_MODE_UNAVAILABLE,
    EV_MODE_WAITING,
    EV_PAUSE_CURRENT,
    EV_POWER_MEDIAN_WINDOW,
    EV_RESTART_DELAY,
    EV_START_CURRENT,
    EV_STOP_CURRENT,
    EV_STOP_DELAY,
    EV_UPDATE_INTERVAL,
    MIN_ACTUATION_INTERVAL,
    MODE_UNAVAILABLE,
    UPDATE_INTERVAL,
)
from .ev_calculations import calculate_ev_pv_decision, update_battery_full_hysteresis
from .models import ControlDecision, EVControlDecision
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
        self.ev_decision = EVControlDecision(
            valid=False,
            mode=EV_MODE_UNAVAILABLE,
            reason="GridPilot has not calculated an EV decision yet",
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
        self._ev_actuation_enabled = bool(
            entry.options.get(CONF_ENABLE_EV_ACTUATION, DEFAULT_ENABLE_EV_ACTUATION)
        )
        self._ev_current_limit_entity = entry.options.get(CONF_EV_CURRENT_LIMIT)
        self.last_applied_ev_current: float | None = None
        self.last_ev_actuation_error: str | None = None
        self._last_ev_write_monotonic: float | None = None
        self._ev_requires_pause = False
        self._battery_full = False
        self._ev_stop_started: float | None = None
        self._ev_restart_until: float | None = None
        self._ev_power_samples: deque[tuple[float, float]] = deque()
        self._ev_current_samples: deque[tuple[float, float]] = deque()

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
        source_entities.update(
            value
            for key, value in self.entry.options.items()
            if key
            in {
                CONF_GRID_POWER,
                CONF_EV_POWER,
                CONF_EV_CONNECTION_STATE,
                CONF_EV_CURRENT_LIMIT,
                CONF_EV_CURRENT_FEEDBACK,
                CONF_EV_VOLTAGE,
                CONF_EV_PHASE_MODE,
                CONF_EV_MODE,
                CONF_EV_OVERRIDE,
            }
            and value
        )
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
        if self.entry.options.get(CONF_EV_CURRENT_LIMIT):
            self.entry.async_on_unload(
                async_track_time_interval(
                    self.hass,
                    self._async_periodic_refresh,
                    EV_UPDATE_INTERVAL,
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
                    charge_soc=float(options.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC)),
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

            self._calculate_ev_decision()
            await self._async_apply_decision()
            await self._async_apply_ev_decision()

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

    def _calculate_ev_decision(self) -> None:
        """Calculate one PV-surplus EV-current decision."""
        options = self.entry.options
        required = {
            CONF_GRID_POWER,
            CONF_EV_POWER,
            CONF_EV_CONNECTION_STATE,
            CONF_EV_CURRENT_LIMIT,
            CONF_EV_VOLTAGE,
            CONF_EV_PHASE_MODE,
            CONF_EV_MODE,
        }
        missing = sorted(key for key in required if not options.get(key))
        if missing:
            self.ev_decision = EVControlDecision(
                valid=False,
                mode=EV_MODE_UNAVAILABLE,
                reason=f"EV control is not configured: {', '.join(missing)}",
                requested_current=(
                    EV_PAUSE_CURRENT
                    if self._ev_actuation_enabled and self._ev_current_limit_entity
                    else None
                ),
            )
            return

        try:
            soc = self._numeric_state(self.entry.data[CONF_BATTERY_SOC])
            self._battery_full = update_battery_full_hysteresis(soc, self._battery_full)
            mode = self._state(options[CONF_EV_MODE])
            pv_mode = str(options.get(CONF_EV_PV_MODE, DEFAULT_EV_PV_MODE))
            override = options.get(CONF_EV_OVERRIDE)
            if mode != pv_mode or (override and self._state(override) == "on"):
                self._clear_ev_samples()
                self.ev_decision = EVControlDecision(
                    valid=True,
                    mode=EV_MODE_INACTIVE,
                    reason="EV charging mode is not PV charging",
                    battery_full=self._battery_full,
                )
                return

            connection_state = self._state(options[CONF_EV_CONNECTION_STATE])
            disconnected = str(
                options.get(CONF_EV_DISCONNECTED_STATE, DEFAULT_EV_DISCONNECTED_STATE)
            )
            if connection_state == disconnected:
                self.ev_decision = EVControlDecision(
                    valid=True,
                    mode=EV_MODE_DISCONNECTED,
                    reason="EV is not connected",
                    battery_full=self._battery_full,
                    requested_current=EV_PAUSE_CURRENT,
                )
                return

            if (
                not self.decision.valid
                or (self.decision.requested_grid_setpoint or 0) > 0
            ):
                self.ev_decision = EVControlDecision(
                    valid=True,
                    mode=EV_MODE_BLOCKED,
                    reason="Battery grid charging blocks PV EV charging",
                    battery_full=self._battery_full,
                    requested_current=EV_PAUSE_CURRENT,
                )
                return

            self._validate_ev_actuator()
            phase_count = self._phase_count(options[CONF_EV_PHASE_MODE])
            battery_power = self._power_state(self.entry.data[CONF_BATTERY_POWER])
            if not bool(
                options.get(
                    CONF_BATTERY_CHARGE_POSITIVE,
                    DEFAULT_BATTERY_CHARGE_POSITIVE,
                )
            ):
                battery_power = -battery_power
            raw = calculate_ev_pv_decision(
                ev_power=self._power_state(options[CONF_EV_POWER]),
                battery_power=battery_power,
                grid_power=self._power_state(options[CONF_GRID_POWER]),
                voltage=self._numeric_state(options[CONF_EV_VOLTAGE]),
                phase_count=phase_count,
                priority=float(options.get(CONF_EV_PRIORITY, DEFAULT_EV_PRIORITY)),
                max_current=float(
                    options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
                ),
                safety_margin=float(
                    options.get(CONF_PV_SAFETY_MARGIN, DEFAULT_PV_SAFETY_MARGIN)
                ),
                battery_full=self._battery_full,
            )
            now = monotonic()
            available = self._sample_median(
                self._ev_power_samples,
                raw.available_pv_power or 0,
                EV_POWER_MEDIAN_WINDOW.total_seconds(),
                now,
            )
            smoothed = calculate_ev_pv_decision(
                ev_power=0,
                battery_power=available,
                grid_power=0,
                voltage=self._numeric_state(options[CONF_EV_VOLTAGE]),
                phase_count=phase_count,
                priority=float(options.get(CONF_EV_PRIORITY, DEFAULT_EV_PRIORITY)),
                max_current=float(
                    options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
                ),
                safety_margin=0,
                battery_full=self._battery_full,
            )
            target = smoothed.target_current or 0
            target_median = self._sample_median(
                self._ev_current_samples,
                target,
                EV_CURRENT_MEDIAN_WINDOW.total_seconds(),
                now,
            )
            requested, control_mode, reason = self._ev_requested_current(
                current=self._current_state(
                    options.get(CONF_EV_CURRENT_FEEDBACK)
                    or options[CONF_EV_CURRENT_LIMIT]
                ),
                target=target,
                target_median=target_median,
                max_current=float(
                    options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
                ),
                now=now,
            )
            self.ev_decision = replace(
                smoothed,
                mode=control_mode,
                reason=reason,
                requested_current=requested,
            )
        except (KeyError, TypeError, ValueError) as err:
            self.ev_decision = EVControlDecision(
                valid=False,
                mode=EV_MODE_UNAVAILABLE,
                reason=str(err),
                battery_full=self._battery_full,
                requested_current=EV_PAUSE_CURRENT,
            )

    def _ev_requested_current(
        self,
        *,
        current: float,
        target: float,
        target_median: float,
        max_current: float,
        now: float,
    ) -> tuple[float, str, str]:
        """Apply EV start/stop hysteresis, ramping and deadband."""
        if current < EV_MIN_CURRENT:
            if self._ev_restart_until and now < self._ev_restart_until:
                return (
                    EV_PAUSE_CURRENT,
                    EV_MODE_RESTART_BLOCKED,
                    "EV restart delay is active",
                )
            if target >= EV_START_CURRENT and target_median >= EV_START_CURRENT:
                self._ev_stop_started = None
                return EV_MIN_CURRENT, EV_MODE_CHARGING, "PV charging started"
            return EV_PAUSE_CURRENT, EV_MODE_WAITING, "Waiting for sufficient PV power"

        if target < EV_STOP_CURRENT:
            if self._ev_stop_started is None:
                self._ev_stop_started = now
            if now - self._ev_stop_started >= EV_STOP_DELAY.total_seconds():
                self._ev_stop_started = None
                self._ev_restart_until = now + EV_RESTART_DELAY.total_seconds()
                return (
                    EV_PAUSE_CURRENT,
                    EV_MODE_RESTART_BLOCKED,
                    "PV stop delay elapsed",
                )
            return (
                min(
                    max_current,
                    max(EV_MIN_CURRENT, current - EV_CURRENT_STEP),
                ),
                EV_MODE_STOP_DELAY,
                "Temporary PV shortage is buffered",
            )

        self._ev_stop_started = None
        bounded = min(max_current, max(EV_MIN_CURRENT, target))
        if bounded >= current + EV_CURRENT_DEADBAND:
            requested = min(max_current, current + EV_CURRENT_STEP)
        elif bounded <= current - EV_CURRENT_DEADBAND:
            requested = min(
                max_current,
                max(EV_MIN_CURRENT, current - EV_CURRENT_STEP),
            )
        else:
            requested = current
        return requested, EV_MODE_CHARGING, "EV current follows available PV power"

    async def _async_apply_ev_decision(self) -> None:
        """Optionally apply the calculated EV current."""
        requested = self.ev_decision.requested_current
        if not self._ev_actuation_enabled:
            if self._ev_requires_pause:
                try:
                    await self._async_write_ev_current(EV_PAUSE_CURRENT, force=True)
                except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
                    self.last_ev_actuation_error = str(err)
            else:
                self.last_ev_actuation_error = None
            return

        if requested is None:
            if self._ev_requires_pause:
                requested = EV_PAUSE_CURRENT
            else:
                self.last_ev_actuation_error = None
                return

        try:
            await self._async_write_ev_current(
                requested, force=not self.ev_decision.valid
            )
        except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
            self.last_ev_actuation_error = str(err)
            _LOGGER.error("Unable to apply GridPilot EV current: %s", err)

    async def _async_write_ev_current(
        self, requested: float, *, force: bool = False
    ) -> None:
        """Validate and write one EV current through Home Assistant."""
        entity_id = self._ev_current_limit_entity
        if not isinstance(entity_id, str):
            raise ValueError("EV current limit is not configured")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"EV current limit is unavailable: {entity_id}")
        if state.attributes.get("unit_of_measurement") != "A":
            raise ValueError(f"EV current limit is not measured in A: {entity_id}")
        if "min" not in state.attributes or "max" not in state.attributes:
            raise ValueError(f"EV current limit has no numeric limits: {entity_id}")

        current = float(state.state)
        minimum = float(state.attributes["min"])
        maximum = float(state.attributes["max"])
        if not minimum <= requested <= maximum:
            raise ValueError(
                f"EV current {requested} A is outside {minimum}..{maximum} A"
            )
        if math.isclose(current, requested, abs_tol=0.05):
            self.last_applied_ev_current = requested
            self.last_ev_actuation_error = None
            self._ev_requires_pause = requested > EV_PAUSE_CURRENT
            return

        now = monotonic()
        if (
            not force
            and self._last_ev_write_monotonic is not None
            and now - self._last_ev_write_monotonic
            < MIN_ACTUATION_INTERVAL.total_seconds()
        ):
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": requested},
            blocking=True,
        )
        self.last_applied_ev_current = requested
        self.last_ev_actuation_error = None
        self._last_ev_write_monotonic = now
        self._ev_requires_pause = requested > EV_PAUSE_CURRENT

    def _validate_ev_actuator(self) -> None:
        """Ensure the EV actuator supports both pause and configured maximum."""
        entity_id = self._ev_current_limit_entity
        if not isinstance(entity_id, str):
            raise ValueError("EV current limit is not configured")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"EV current limit is unavailable: {entity_id}")
        if state.attributes.get("unit_of_measurement") != "A":
            raise ValueError(f"EV current limit is not measured in A: {entity_id}")
        if "min" not in state.attributes or "max" not in state.attributes:
            raise ValueError(f"EV current limit has no numeric limits: {entity_id}")
        minimum = float(state.attributes["min"])
        maximum = float(state.attributes["max"])
        configured_maximum = float(
            self.entry.options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
        )
        if not minimum <= EV_PAUSE_CURRENT <= maximum:
            raise ValueError("EV current limit must support the safe 5 A pause value")
        if configured_maximum > maximum:
            raise ValueError(
                f"Configured EV maximum {configured_maximum} A exceeds {maximum} A"
            )

    def _state(self, entity_id: str) -> str:
        """Return one available Home Assistant state."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Entity is unavailable: {entity_id}")
        return state.state

    def _phase_count(self, entity_id: str) -> int:
        """Convert a phase select or numeric sensor state to 1 or 3."""
        value = self._state(entity_id)
        if value.startswith("1"):
            return 1
        if value.startswith("3"):
            return 3
        raise ValueError(f"EV phase state must represent 1 or 3 phases: {value}")

    @staticmethod
    def _sample_median(
        samples: deque[tuple[float, float]],
        value: float,
        window: float,
        now: float,
    ) -> float:
        """Add one sample and return the median inside a monotonic time window."""
        samples.append((now, value))
        threshold = now - window
        while samples and samples[0][0] < threshold:
            samples.popleft()
        return float(median(sample for _, sample in samples))

    def _clear_ev_samples(self) -> None:
        """Clear smoothing state when PV mode is not active."""
        self._ev_power_samples.clear()
        self._ev_current_samples.clear()
        self._ev_stop_started = None

    async def async_shutdown(self) -> bool:
        """Return active battery and EV actuators to neutral setpoints."""
        async with self._refresh_lock:
            success = True
            if self._actuation_enabled or self._requires_neutralization:
                try:
                    await self._async_write_setpoint(0.0, force=True)
                except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
                    self.last_actuation_error = str(err)
                    success = False
                    _LOGGER.warning(
                        "Unable to reset GridPilot setpoint during unload: %s", err
                    )
            self._actuation_enabled = False

            if self._ev_current_limit_entity and (
                self._ev_actuation_enabled or self._ev_requires_pause
            ):
                try:
                    await self._async_write_ev_current(EV_PAUSE_CURRENT, force=True)
                except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
                    self.last_ev_actuation_error = str(err)
                    success = False
                    _LOGGER.warning(
                        "Unable to pause GridPilot EV control during unload: %s", err
                    )
            self._ev_actuation_enabled = False

            if not success:
                for listener in tuple(self._listeners):
                    listener()
            return success

    def _numeric_state(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Entity is unavailable: {entity_id}")
        value = float(state.state)
        if not math.isfinite(value):
            raise ValueError(f"Entity is not numeric: {entity_id}")
        return value

    def _current_state(self, entity_id: str) -> float:
        """Return one finite current state measured in amperes."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Current entity is unavailable: {entity_id}")
        if state.attributes.get("unit_of_measurement") != "A":
            raise ValueError(f"Current entity is not measured in A: {entity_id}")
        value = float(state.state)
        if not math.isfinite(value):
            raise ValueError(f"Current entity is not numeric: {entity_id}")
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
    def ev_actuation_enabled(self) -> bool:
        """Return whether GridPilot may write the configured EV current."""
        return self._ev_actuation_enabled

    @property
    def ev_actuation_healthy(self) -> bool:
        """Return whether EV current control has applied without an error."""
        return self.last_ev_actuation_error is None

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
            "ev_decision": {
                "valid": self.ev_decision.valid,
                "mode": self.ev_decision.mode,
                "reason": self.ev_decision.reason,
                "battery_full": self.ev_decision.battery_full,
                "available_pv_power": self.ev_decision.available_pv_power,
                "allocated_ev_power": self.ev_decision.allocated_ev_power,
                "target_current": self.ev_decision.target_current,
                "requested_current": self.ev_decision.requested_current,
                "phase_count": self.ev_decision.phase_count,
            },
            "ev_actuation": {
                "enabled": self.ev_actuation_enabled,
                "healthy": self.ev_actuation_healthy,
                "last_applied_current": self.last_applied_ev_current,
                "last_error": self.last_ev_actuation_error,
                "pause_pending": self._ev_requires_pause,
            },
            "shadow_mode": not self.actuation_enabled,
            "ev_shadow_mode": not self.ev_actuation_enabled,
        }
