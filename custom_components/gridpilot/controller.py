"""GridPilot battery controller."""

from __future__ import annotations

import asyncio
import logging
import math
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from statistics import median
from time import monotonic
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .calculations import BatteryCurve, calculate_battery_decision, normalize_power
from .capacity import CapacitySample, update_capacity_sample
from .const import (
    CONF_AUTO_CHARGE_SOC_SOLAR,
    CONF_AUTO_CHARGE_SOC_SOLAR_EV,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_ENERGY,
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_DISCHARGE_ENERGY,
    CONF_BATTERY_ENERGY,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CAPACITY_CALIBRATION,
    CONF_CHARGE_SOC,
    CONF_ENABLE_ACTUATION,
    CONF_ENABLE_EV_ACTUATION,
    CONF_ENABLE_SOC_LOAD_ACTUATION,
    CONF_EV_BATTERY_CAPACITY,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_SOC,
    CONF_EV_BATTERY_TARGET_TIME,
    CONF_EV_BATTERY_TIME_TO_GO,
    CONF_EV_CHARGE_ENERGY,
    CONF_EV_CONNECTION_STATE,
    CONF_EV_CURRENT_FEEDBACK,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_DEPARTURE_TARGET_SOC,
    CONF_EV_DEPARTURE_TIME,
    CONF_EV_DISCHARGE_ENERGY,
    CONF_EV_LAST_SAFE_CURRENT,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_MAX_CURRENT,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_PRIORITY,
    CONF_EV_SOC_CALCULATION,
    CONF_EV_VEHICLE_SOC,
    CONF_EV_VOLTAGE,
    CONF_GRID_POWER,
    CONF_GRID_SETPOINT,
    CONF_GRIDPILOT_EV_MODE,
    CONF_HOME_LOAD,
    CONF_HOME_LOAD_L1,
    CONF_HOME_LOAD_L2,
    CONF_HOME_LOAD_L3,
    CONF_MAX_GRID_POWER,
    CONF_PV_SAFETY_MARGIN,
    CONF_SOC_LOAD_ENTITIES,
    CONF_SOC_LOAD_OFF_THRESHOLD,
    CONF_SOC_LOAD_ON_THRESHOLD,
    CONSUMPTION_FORECAST_REMAINING_ENTITY,
    DEFAULT_AUTO_CHARGE_SOC_SOLAR,
    DEFAULT_AUTO_CHARGE_SOC_SOLAR_EV,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_CHARGE_SOC,
    DEFAULT_ENABLE_ACTUATION,
    DEFAULT_ENABLE_EV_ACTUATION,
    DEFAULT_ENABLE_SOC_LOAD_ACTUATION,
    DEFAULT_EV_BATTERY_CAPACITY,
    DEFAULT_EV_BATTERY_MODE,
    DEFAULT_EV_DEPARTURE_MODE,
    DEFAULT_EV_DEPARTURE_TARGET_SOC,
    DEFAULT_EV_DEPARTURE_TIME,
    DEFAULT_EV_DISCONNECTED_STATE,
    DEFAULT_EV_MANUAL_MODE,
    DEFAULT_EV_MAX_CURRENT,
    DEFAULT_EV_MODE,
    DEFAULT_EV_OFF_MODE,
    DEFAULT_EV_PRIORITY,
    DEFAULT_EV_PV_MODE,
    DEFAULT_MAX_GRID_POWER,
    DEFAULT_PV_SAFETY_MARGIN,
    DEFAULT_SOC_LOAD_OFF_THRESHOLD,
    DEFAULT_SOC_LOAD_ON_THRESHOLD,
    DEPARTURE_BATTERY_HIGH_DELAY,
    DEPARTURE_BATTERY_POWER_DEADBAND,
    DEPARTURE_SETPOINT_INTERVAL,
    DEPARTURE_SETPOINT_STEP,
    EV_CHARGING_EFFICIENCY,
    EV_CURRENT_DEADBAND,
    EV_CURRENT_MEDIAN_WINDOW,
    EV_DEPARTURE_CURRENT_STEP,
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
    EV_PV_CURRENT_STEP,
    EV_RESTART_DELAY,
    EV_START_CURRENT,
    EV_STOP_CURRENT,
    EV_STOP_DELAY,
    EV_STRATEGY_BATTERY_TO_EV,
    EV_STRATEGY_DEPARTURE,
    EV_STRATEGY_MANUAL,
    EV_STRATEGY_NONE,
    EV_STRATEGY_PV,
    EV_UPDATE_INTERVAL,
    INPUT_MAX_SETTLE_DELAY,
    INPUT_SETTLE_DELAY,
    MIN_ACTUATION_INTERVAL,
    MODE_UNAVAILABLE,
    PV_FORECAST_REMAINING_ENTITY,
    SOC_LOAD_DOMAINS,
    UPDATE_INTERVAL,
)
from .ev_calculations import (
    calculate_battery_to_ev_decision,
    calculate_departure_ev_decision,
    calculate_ev_pv_decision,
    calculate_manual_ev_decision,
    update_battery_full_hysteresis,
)
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
        self._tracked_source_entities: set[str] = set()
        self._input_snapshot: dict[str, State | None] | None = None
        self._pending_refresh_task: asyncio.Task[None] | None = None
        self._refresh_batch_started: float | None = None
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
        last_safe_current = entry.options.get(CONF_EV_LAST_SAFE_CURRENT)
        self._last_safe_ev_current = (
            float(last_safe_current)
            if isinstance(last_safe_current, int | float)
            else None
        )
        self.last_ev_actuation_error: str | None = None
        self._last_ev_write_monotonic: float | None = None
        self._ev_requires_pause = False
        self._ev_current_limit_unavailable: bool | None = None
        self._last_ev_strategy = EV_STRATEGY_NONE
        self._battery_full = False
        self._ev_stop_started: float | None = None
        self._ev_restart_until: float | None = None
        self._ev_power_samples: deque[tuple[float, float]] = deque()
        self._ev_current_samples: deque[tuple[float, float]] = deque()
        self._skip_next_options_reload = 0
        self._soc_load_actuation_enabled = bool(
            entry.options.get(
                CONF_ENABLE_SOC_LOAD_ACTUATION, DEFAULT_ENABLE_SOC_LOAD_ACTUATION
            )
        )
        self.last_soc_load_actuation_error: str | None = None
        self.departure_battery_power: float | None = None
        self._departure_grid_setpoint: float | None = None
        self._last_departure_setpoint_adjustment: float | None = None
        self._departure_battery_high_since: float | None = None
        self._departure_battery_low_since: float | None = None
        self._departure_ev_current: float | None = None
        self._departure_ev_plan: tuple[float | int | str, ...] | None = None
        self._calculated_ev_soc: float | None = None
        self._last_measured_ev_soc: float | None = None
        self._ev_soc_anchor_soc: float | None = None
        self._ev_soc_anchor_energy: float | None = None
        self._ev_soc_anchor_updated: float | None = None
        self._ev_soc_error = "EV SOC calculation has not run yet"
        ev_soc_calculation = entry.options.get(CONF_EV_SOC_CALCULATION, {})
        if isinstance(ev_soc_calculation, dict):
            try:
                anchor_soc = float(ev_soc_calculation["soc"])
                anchor_energy = float(ev_soc_calculation["energy"])
                anchor_updated = float(ev_soc_calculation["updated"])
                if (
                    0 <= anchor_soc <= 100
                    and anchor_energy >= 0
                    and math.isfinite(anchor_updated)
                ):
                    self._last_measured_ev_soc = anchor_soc
                    self._ev_soc_anchor_soc = anchor_soc
                    self._ev_soc_anchor_energy = anchor_energy
                    self._ev_soc_anchor_updated = anchor_updated
            except (KeyError, TypeError, ValueError):
                pass
        calibration = entry.options.get(CONF_CAPACITY_CALIBRATION, {})
        self._capacity_calibration: dict[str, CapacitySample] = (
            calibration if isinstance(calibration, dict) else {}
        )

    async def async_update_ev_priority(self, value: float) -> None:
        """Update EV priority without pausing the active EV charger."""
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, CONF_EV_PRIORITY: value},
        )
        await self.async_refresh()

    async def async_update_ev_mode(self, value: str) -> None:
        """Persist the GridPilot-owned EV charging mode."""
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, CONF_GRIDPILOT_EV_MODE: value},
        )
        await self.async_refresh()

    async def async_update_ev_option(self, key: str, value: float) -> None:
        """Persist one GridPilot-owned EV departure setting."""
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, key: value}
        )
        await self.async_refresh()

    async def async_update_auto_charge_soc_mode(
        self, option: str, enabled: bool
    ) -> None:
        """Persist an exclusive automatic charge-SOC mode."""
        options = {**self.entry.options, option: enabled}
        if enabled:
            other_option = (
                CONF_AUTO_CHARGE_SOC_SOLAR_EV
                if option == CONF_AUTO_CHARGE_SOC_SOLAR
                else CONF_AUTO_CHARGE_SOC_SOLAR
            )
            options[other_option] = False
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        await self.async_refresh()

    def consume_options_reload_skip(self) -> bool:
        """Return and clear the one-shot reload suppression flag."""
        if not self._skip_next_options_reload:
            return False
        self._skip_next_options_reload -= 1
        return True

    async def async_start(self) -> None:
        """Start state and interval tracking."""
        if (
            self.entry.options.get(CONF_AUTO_CHARGE_SOC_SOLAR)
            and self.entry.options.get(CONF_AUTO_CHARGE_SOC_SOLAR_EV)
        ):
            self._skip_next_options_reload += 1
            self.hass.config_entries.async_update_entry(
                self.entry,
                options={**self.entry.options, CONF_AUTO_CHARGE_SOC_SOLAR: False},
            )
        source_entities = {
            value
            for key, value in self.entry.data.items()
            if key
            in {
                CONF_BATTERY_SOC,
                CONF_BATTERY_POWER,
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
                CONF_EV_VEHICLE_SOC,
                CONF_EV_CONNECTION_STATE,
                CONF_EV_CURRENT_LIMIT,
                CONF_EV_CURRENT_FEEDBACK,
                CONF_EV_VOLTAGE,
                CONF_EV_PHASE_MODE,
                CONF_EV_MANUAL_CURRENT,
                CONF_EV_BATTERY_SOC,
                CONF_EV_BATTERY_MIN_SOC,
                CONF_EV_BATTERY_TIME_TO_GO,
                CONF_EV_BATTERY_TARGET_TIME,
                CONF_BATTERY_ENERGY,
                CONF_BATTERY_CHARGE_ENERGY,
                CONF_BATTERY_DISCHARGE_ENERGY,
                CONF_EV_CHARGE_ENERGY,
                CONF_EV_DISCHARGE_ENERGY,
            }
            and value
        )
        source_entities.update(
            {
                PV_FORECAST_REMAINING_ENTITY,
                CONSUMPTION_FORECAST_REMAINING_ENTITY,
            }
        )
        self._tracked_source_entities = set(source_entities)
        if grid_setpoint := self.entry.data.get(CONF_GRID_SETPOINT):
            self._tracked_source_entities.add(grid_setpoint)
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
                EV_UPDATE_INTERVAL
                if self._ev_current_limit_entity
                else UPDATE_INTERVAL,
            )
        )
        self.entry.async_on_unload(self._cancel_pending_refresh)
        self._schedule_debounced_refresh()

    async def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Coalesce related source updates before refreshing."""
        entity_id = event.data["entity_id"]
        if entity_id == self._ev_current_limit_entity:
            self._log_ev_current_limit_availability(event.data["new_state"])
        if (
            entity_id == self.entry.options.get(CONF_GRID_POWER)
            and not self._battery_full
        ):
            return
        self._schedule_debounced_refresh()

    @callback
    def _schedule_debounced_refresh(self) -> None:
        """Refresh after inputs settle, but never postpone a batch indefinitely."""
        now = monotonic()
        if self._refresh_batch_started is None:
            self._refresh_batch_started = now
        deadline = (
            self._refresh_batch_started
            + INPUT_MAX_SETTLE_DELAY.total_seconds()
        )
        run_at = min(now + INPUT_SETTLE_DELAY.total_seconds(), deadline)

        if self._pending_refresh_task is not None:
            self._pending_refresh_task.cancel()
        self._pending_refresh_task = self.hass.async_create_task(
            self._async_debounced_refresh(max(0.0, run_at - now))
        )

    async def _async_debounced_refresh(self, delay: float) -> None:
        """Run one refresh for a settled or expired batch of input updates."""
        task = asyncio.current_task()
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        if self._pending_refresh_task is task:
            self._pending_refresh_task = None
            self._refresh_batch_started = None
        await self.async_refresh()

    @callback
    def _cancel_pending_refresh(self) -> None:
        """Cancel delayed work while unloading the config entry."""
        if self._pending_refresh_task is not None:
            self._pending_refresh_task.cancel()
            self._pending_refresh_task = None
        self._refresh_batch_started = None

    def _log_ev_current_limit_availability(self, state: Any) -> None:
        """Log transitions of the EV current-limit entity without poll spam."""
        unavailable = state is None or state.state in {"unknown", "unavailable"}
        if unavailable == self._ev_current_limit_unavailable:
            return
        self._ev_current_limit_unavailable = unavailable
        if unavailable:
            _LOGGER.warning(
                "GridPilot EV current limit became unavailable: entity=%s state=%s "
                "last_updated=%s requested=%s strategy=%s reason=%s",
                self._ev_current_limit_entity,
                None if state is None else state.state,
                None if state is None else state.last_updated.isoformat(),
                self.ev_decision.requested_current,
                self.ev_decision.strategy,
                self.ev_decision.reason,
            )
            return
        else:
            assert state is not None
            _LOGGER.warning(
                "GridPilot EV current limit recovered: entity=%s state=%s "
                "last_updated=%s",
                self._ev_current_limit_entity,
                state.state,
                state.last_updated.isoformat(),
            )

    async def _async_periodic_refresh(self, now: datetime) -> None:
        """Schedule a coordinated refresh on the fallback interval."""
        self._schedule_debounced_refresh()

    async def async_refresh(self) -> None:
        """Calculate, optionally apply and publish one new decision."""
        async with self._refresh_lock:
            self._input_snapshot = {
                entity_id: self.hass.states.get(entity_id)
                for entity_id in self._tracked_source_entities
            }
            try:
                self._update_calculated_ev_soc()
                try:
                    self._update_auto_charge_soc()
                    soc = self._numeric_state(self.entry.data[CONF_BATTERY_SOC])
                    home_load = self._home_load()
                    options = self.entry.options
                    max_grid_power = self._max_grid_power()
                    curve = BatteryCurve(
                        charge_soc=float(
                            options.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC)
                        ),
                        minimum_charge_power=max_grid_power * 0.1,
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
                await self._async_calibrate_capacities()
                self._apply_departure_grid_plan()
                await self._async_apply_decision()
                await self._async_apply_ev_decision()
                await self._async_apply_soc_load_decision()

                for listener in tuple(self._listeners):
                    listener()
            finally:
                self._input_snapshot = None

    def _update_auto_charge_soc(self) -> None:
        """Update the charge SOC from valid remaining-energy forecasts."""
        options = self.entry.options
        solar_mode = bool(
            options.get(CONF_AUTO_CHARGE_SOC_SOLAR, DEFAULT_AUTO_CHARGE_SOC_SOLAR)
        )
        solar_ev_mode = bool(
            options.get(
                CONF_AUTO_CHARGE_SOC_SOLAR_EV,
                DEFAULT_AUTO_CHARGE_SOC_SOLAR_EV,
            )
        )
        if not solar_mode and not solar_ev_mode:
            return

        try:
            production = self._energy_state(PV_FORECAST_REMAINING_ENTITY)
            consumption = self._energy_state(CONSUMPTION_FORECAST_REMAINING_ENTITY)
            battery_capacity = float(
                options.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY)
            )
            if battery_capacity <= 0:
                raise ValueError("Usable home-battery capacity must be positive")

            ev_needed = 0.0
            if solar_ev_mode:
                if self._calculated_ev_soc is None:
                    raise ValueError("EV SOC is unavailable")
                ev_capacity = float(
                    options.get(CONF_EV_BATTERY_CAPACITY, DEFAULT_EV_BATTERY_CAPACITY)
                )
                ev_target = float(
                    options.get(
                        CONF_EV_DEPARTURE_TARGET_SOC,
                        DEFAULT_EV_DEPARTURE_TARGET_SOC,
                    )
                )
                ev_needed = (
                    ev_capacity * max(0.0, ev_target - self._calculated_ev_soc) / 100
                )

            deficit = max(0.0, consumption + ev_needed - production)
            target = max(15.0, min(95.0, 15.0 + deficit / battery_capacity * 100))
            target = round(target / 5) * 5
        except (TypeError, ValueError) as err:
            _LOGGER.debug("Automatic charge SOC keeps the manual value: %s", err)
            return

        current = float(options.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC))
        if math.isclose(current, target, abs_tol=0.001):
            return
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(
            self.entry, options={**options, CONF_CHARGE_SOC: target}
        )

    async def _async_calibrate_capacities(self) -> None:
        """Learn usable capacity from SOC changes and cumulative energy meters."""
        options = self.entry.options
        changed = False
        for name, soc_entity, charge_key, discharge_key in (
            (
                "home",
                self.entry.data[CONF_BATTERY_SOC],
                CONF_BATTERY_CHARGE_ENERGY,
                CONF_BATTERY_DISCHARGE_ENERGY,
            ),
            (
                "ev",
                options.get(CONF_EV_VEHICLE_SOC),
                CONF_EV_CHARGE_ENERGY,
                CONF_EV_DISCHARGE_ENERGY,
            ),
        ):
            if not isinstance(soc_entity, str):
                continue
            charge_entity = options.get(charge_key)
            discharge_entity = options.get(discharge_key)
            if not isinstance(charge_entity, str) and not isinstance(
                discharge_entity, str
            ):
                continue
            try:
                sample = update_capacity_sample(
                    self._capacity_calibration.get(name),
                    soc=self._numeric_state(soc_entity),
                    charge_energy=(
                        self._energy_state(charge_entity)
                        if isinstance(charge_entity, str)
                        else 0.0
                    ),
                    discharge_energy=(
                        self._energy_state(discharge_entity)
                        if isinstance(discharge_entity, str)
                        else 0.0
                    ),
                    charging_only=name == "ev",
                )
            except ValueError:
                continue
            if sample != self._capacity_calibration.get(name):
                self._capacity_calibration[name] = sample
                changed = True
        if changed:
            self._skip_next_options_reload += 1
            self.hass.config_entries.async_update_entry(
                self.entry,
                options={
                    **options,
                    CONF_CAPACITY_CALIBRATION: self._capacity_calibration,
                },
            )

    def learned_capacity(self, battery: str) -> float | None:
        """Return a learned usable capacity once a valid calibration exists."""
        sample = self._capacity_calibration.get(battery)
        if sample and sample["capacity"] > 0:
            return sample["capacity"]
        return None

    def _apply_departure_grid_plan(self) -> None:
        """Steer measured battery discharge gradually toward the departure plan."""
        self.departure_battery_power = None
        actuator_unavailable = (
            self.ev_decision.strategy == EV_STRATEGY_DEPARTURE
            and self.ev_decision.reason.startswith("EV current limit is unavailable")
        )
        if (
            self.ev_decision.strategy != EV_STRATEGY_DEPARTURE
            or not self.ev_decision.valid
            or self.ev_decision.requested_current is None
            or self.ev_decision.phase_count is None
        ):
            self._last_departure_setpoint_adjustment = None
            self._departure_grid_setpoint = None
            if not actuator_unavailable:
                self._departure_ev_current = None
                self._departure_ev_plan = None
            return
        try:
            battery_target = self._departure_battery_power()
            actual_discharge = self._departure_battery_discharge_power()
            actual_setpoint = self._current_grid_setpoint()
            current_setpoint = self._departure_grid_setpoint or actual_setpoint
            now = monotonic()
            adjustment_due = (
                self._last_departure_setpoint_adjustment is None
                or now - self._last_departure_setpoint_adjustment
                >= DEPARTURE_SETPOINT_INTERVAL.total_seconds()
            )
            deviation = actual_discharge - battery_target
            if deviation > DEPARTURE_BATTERY_POWER_DEADBAND:
                self._departure_battery_high_since = (
                    self._departure_battery_high_since or now
                )
            else:
                self._departure_battery_high_since = None
            if deviation < -DEPARTURE_BATTERY_POWER_DEADBAND:
                self._departure_battery_low_since = (
                    self._departure_battery_low_since or now
                )
            else:
                self._departure_battery_low_since = None
            high_ready = (
                self._departure_battery_high_since is not None
                and now - self._departure_battery_high_since
                >= DEPARTURE_BATTERY_HIGH_DELAY.total_seconds()
            )
            low_ready = (
                self._departure_battery_low_since is not None
                and now - self._departure_battery_low_since
                >= DEPARTURE_BATTERY_HIGH_DELAY.total_seconds()
            )
            max_current = float(
                self.entry.options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
            )
            target_current = min(
                max_current, self.ev_decision.target_current or EV_PAUSE_CURRENT
            )
            deadline_risk = (self.ev_decision.target_current or 0.0) > max_current
            current = self._departure_ev_current or self.ev_decision.requested_current
            target_setpoint = (
                self._max_grid_power()
                if deadline_risk
                else min(
                    self._max_grid_power(), max(0.0, actual_setpoint + deviation)
                )
            )
            if deadline_risk:
                requested = self._max_grid_power()
            elif adjustment_due and high_ready:
                requested = current_setpoint + DEPARTURE_SETPOINT_STEP
                self._last_departure_setpoint_adjustment = now
            elif adjustment_due and low_ready:
                if current is not None and current < target_current:
                    requested = current_setpoint
                else:
                    requested = current_setpoint - DEPARTURE_SETPOINT_STEP
                    self._last_departure_setpoint_adjustment = now
            else:
                requested = current_setpoint
            requested = min(self._max_grid_power(), max(0.0, requested))
        except (KeyError, TypeError, ValueError):
            if self._departure_grid_setpoint is not None:
                self.decision = replace(
                    self.decision,
                    requested_grid_setpoint=self._departure_grid_setpoint,
                    calculated_grid_setpoint=self._departure_grid_setpoint,
                    reason="Grid setpoint steers home battery toward departure reserve",
                )
            return

        if (
            adjustment_due
            and self._departure_battery_high_since is not None
            and now - self._departure_battery_high_since
            >= DEPARTURE_BATTERY_HIGH_DELAY.total_seconds()
            and actual_discharge > battery_target + DEPARTURE_BATTERY_POWER_DEADBAND
            and math.isclose(requested, self._max_grid_power(), abs_tol=1.0)
        ):
            if current is not None and current > EV_MIN_CURRENT:
                self._departure_ev_current = round(
                    max(EV_MIN_CURRENT, current - EV_DEPARTURE_CURRENT_STEP), 2
                )
                self.ev_decision = replace(
                    self.ev_decision,
                    reason="EV current reduced because grid setpoint is saturated",
                    requested_current=self._departure_ev_current,
                )
        elif (
            adjustment_due
            and low_ready
            and current is not None
            and current < target_current
        ):
            self._departure_ev_current = round(
                min(target_current, current + EV_DEPARTURE_CURRENT_STEP),
                2,
            )
            self.ev_decision = replace(
                self.ev_decision,
                reason="EV current increased because battery discharge is below plan",
                requested_current=self._departure_ev_current,
            )
            self._last_departure_setpoint_adjustment = now
        self.departure_battery_power = round(battery_target, 1)
        self._departure_grid_setpoint = float(round(requested / 10) * 10)
        self.decision = replace(
            self.decision,
            requested_grid_setpoint=self._departure_grid_setpoint,
            calculated_grid_setpoint=round(target_setpoint, 1),
            reason=(
                "Grid setpoint stays at maximum while the EV deadline is at risk"
                if deadline_risk
                else "Grid setpoint steers home battery toward departure reserve"
            ),
        )

    def _departure_battery_discharge_power(self) -> float:
        """Return actual home-battery discharge power as a positive watt value."""
        power = self._power_state(self.entry.data[CONF_BATTERY_POWER])
        if not bool(
            self.entry.options.get(
                CONF_BATTERY_CHARGE_POSITIVE, DEFAULT_BATTERY_CHARGE_POSITIVE
            )
        ):
            power = -power
        return max(0.0, -power)

    def _current_grid_setpoint(self) -> float:
        """Return the current Victron grid setpoint in watts."""
        entity_id = self.entry.data[CONF_GRID_SETPOINT]
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Grid setpoint is unavailable: {entity_id}")
        return normalize_power(
            float(state.state), state.attributes.get("unit_of_measurement")
        )

    def _departure_battery_power(self) -> float:
        """Return battery power that reaches the compensation SOC at departure."""
        soc = self._numeric_state(self.entry.data[CONF_BATTERY_SOC])
        reserve_soc = float(
            self.entry.options.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC)
        )
        if soc <= reserve_soc:
            return 0.0
        remaining_energy = self._home_battery_energy()
        if remaining_energy <= 0:
            return 0.0
        available_energy = remaining_energy * (soc - reserve_soc) / soc
        return available_energy * 3_600_000 / self._seconds_until_departure()

    def _home_battery_energy(self) -> float:
        """Return measured or SOC-derived remaining home battery energy in kWh."""
        entity_id = self.entry.options.get(CONF_BATTERY_ENERGY)
        if isinstance(entity_id, str):
            return self._energy_state(entity_id)
        capacity = float(
            self.entry.options.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY)
        )
        return capacity * self._numeric_state(self.entry.data[CONF_BATTERY_SOC]) / 100

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
        """Select and calculate one EV charging strategy."""
        options = self.entry.options
        strategy = EV_STRATEGY_NONE
        common = {CONF_EV_CONNECTION_STATE, CONF_EV_CURRENT_LIMIT}
        missing = sorted(key for key in common if not options.get(key))
        if missing:
            self._set_unavailable_ev_decision(
                f"EV control is not configured: {', '.join(missing)}", strategy
            )
            return

        try:
            strategy = self._selected_ev_strategy(options)
            if strategy == EV_STRATEGY_NONE:
                self._clear_ev_samples()
                self.ev_decision = EVControlDecision(
                    valid=True,
                    mode=EV_MODE_INACTIVE,
                    reason="No GridPilot EV charging strategy is selected",
                )
                return

            connection_state = self._state(options[CONF_EV_CONNECTION_STATE])
            if connection_state == DEFAULT_EV_DISCONNECTED_STATE:
                self._clear_ev_samples()
                self.ev_decision = EVControlDecision(
                    valid=True,
                    mode=EV_MODE_DISCONNECTED,
                    reason="EV is not connected",
                    strategy=strategy,
                    requested_current=EV_PAUSE_CURRENT,
                )
                return

            required = {
                EV_STRATEGY_PV: {
                    CONF_EV_POWER,
                    CONF_EV_VOLTAGE,
                    CONF_EV_PHASE_MODE,
                },
                EV_STRATEGY_MANUAL: {CONF_EV_MANUAL_CURRENT},
                EV_STRATEGY_BATTERY_TO_EV: {
                    CONF_EV_BATTERY_SOC,
                    CONF_EV_BATTERY_MIN_SOC,
                    CONF_EV_BATTERY_TIME_TO_GO,
                    CONF_EV_BATTERY_TARGET_TIME,
                },
                EV_STRATEGY_DEPARTURE: {
                    CONF_EV_VEHICLE_SOC,
                    CONF_EV_VOLTAGE,
                    CONF_EV_PHASE_MODE,
                },
            }[strategy]
            missing = sorted(key for key in required if not options.get(key))
            if missing:
                raise ValueError(
                    f"{strategy} EV control is not configured: {', '.join(missing)}"
                )

            self._validate_ev_actuator()
            if strategy == EV_STRATEGY_PV:
                self._calculate_pv_ev_decision(options)
            elif strategy == EV_STRATEGY_MANUAL:
                self._clear_ev_samples()
                self.ev_decision = calculate_manual_ev_decision(
                    requested_current=self._current_state(
                        options[CONF_EV_MANUAL_CURRENT]
                    ),
                    max_current=float(
                        options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
                    ),
                )
            elif strategy == EV_STRATEGY_DEPARTURE:
                self._clear_ev_samples()
                phase_count = self._phase_count(str(options[CONF_EV_PHASE_MODE]))
                if self._calculated_ev_soc is None:
                    raise ValueError(self._ev_soc_error)
                vehicle_soc = self._calculated_ev_soc
                target_soc = float(
                    options.get(
                        CONF_EV_DEPARTURE_TARGET_SOC,
                        DEFAULT_EV_DEPARTURE_TARGET_SOC,
                    )
                )
                battery_capacity = float(
                    options.get(CONF_EV_BATTERY_CAPACITY, DEFAULT_EV_BATTERY_CAPACITY)
                )
                voltage = self._numeric_state(options[CONF_EV_VOLTAGE])
                max_current = float(
                    options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
                )
                plan = (
                    str(options.get(CONF_EV_DEPARTURE_TIME, DEFAULT_EV_DEPARTURE_TIME)),
                    target_soc,
                    battery_capacity,
                    phase_count,
                    max_current,
                )
                if plan != self._departure_ev_plan:
                    self._departure_ev_current = None
                    self._departure_ev_plan = plan
                decision = calculate_departure_ev_decision(
                    vehicle_soc=vehicle_soc,
                    target_soc=target_soc,
                    battery_capacity_kwh=battery_capacity,
                    seconds_until_departure=self._seconds_until_departure(),
                    voltage=voltage,
                    phase_count=phase_count,
                    max_current=max_current,
                )
                measured_current = self._current_state(
                    options.get(CONF_EV_CURRENT_FEEDBACK)
                    or options[CONF_EV_CURRENT_LIMIT]
                )
                if (
                    decision.requested_current
                    and decision.requested_current > EV_PAUSE_CURRENT
                ):
                    if self._departure_ev_current is None:
                        self._departure_ev_current = round(
                            min(
                                max_current,
                                max(EV_MIN_CURRENT, measured_current),
                            )
                            / EV_DEPARTURE_CURRENT_STEP
                        ) * EV_DEPARTURE_CURRENT_STEP
                elif decision.target_current == EV_PAUSE_CURRENT:
                    self._departure_ev_current = None
                self.ev_decision = replace(
                    decision,
                    mode=(
                        EV_MODE_CHARGING
                        if self._departure_ev_current is not None
                        else decision.mode
                    ),
                    requested_current=self._departure_ev_current or EV_PAUSE_CURRENT,
                )
            else:
                self._clear_ev_samples()
                measured_current = self._current_state(
                    options.get(CONF_EV_CURRENT_FEEDBACK)
                    or options[CONF_EV_CURRENT_LIMIT]
                )
                self.ev_decision = calculate_battery_to_ev_decision(
                    current=(
                        measured_current
                    ),
                    battery_soc=self._numeric_state(self.entry.data[CONF_BATTERY_SOC]),
                    secondary_soc=self._numeric_state(options[CONF_EV_BATTERY_SOC]),
                    minimum_soc=self._numeric_state(options[CONF_EV_BATTERY_MIN_SOC]),
                    time_to_go=self._duration_state(
                        options[CONF_EV_BATTERY_TIME_TO_GO]
                    ),
                    seconds_until_target=self._seconds_until_target(
                        options[CONF_EV_BATTERY_TARGET_TIME]
                    ),
                    max_current=float(
                        options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT)
                    ),
                )
        except (KeyError, TypeError, ValueError) as err:
            self._set_unavailable_ev_decision(str(err), strategy)

    def _selected_ev_strategy(self, options: dict[str, Any]) -> str:
        """Return the selected strategy, with the configured mode taking priority."""
        mode = str(options.get(CONF_GRIDPILOT_EV_MODE, DEFAULT_EV_MODE))
        if mode == DEFAULT_EV_OFF_MODE:
            return EV_STRATEGY_NONE
        if mode == DEFAULT_EV_PV_MODE:
            return EV_STRATEGY_PV
        if mode == DEFAULT_EV_MANUAL_MODE:
            return EV_STRATEGY_MANUAL

        if mode == DEFAULT_EV_BATTERY_MODE:
            battery_options = {
                CONF_EV_BATTERY_SOC,
                CONF_EV_BATTERY_MIN_SOC,
                CONF_EV_BATTERY_TIME_TO_GO,
                CONF_EV_BATTERY_TARGET_TIME,
            }
            return (
                EV_STRATEGY_BATTERY_TO_EV
                if all(options.get(key) for key in battery_options)
                else EV_STRATEGY_NONE
            )
        if mode == DEFAULT_EV_DEPARTURE_MODE:
            return EV_STRATEGY_DEPARTURE
        return EV_STRATEGY_NONE

    def _set_unavailable_ev_decision(self, reason: str, strategy: str) -> None:
        """Publish a fail-safe EV decision for invalid configuration or input."""
        self.ev_decision = EVControlDecision(
            valid=False,
            mode=EV_MODE_UNAVAILABLE,
            reason=reason,
            strategy=strategy,
            battery_full=self._battery_full,
            requested_current=(
                EV_PAUSE_CURRENT
                if self._ev_actuation_enabled and self._ev_current_limit_entity
                else None
            ),
        )

    def _calculate_pv_ev_decision(
        self, options: dict[str, Any]
    ) -> None:
        """Calculate the stateful PV-surplus charging strategy."""
        soc = self._numeric_state(self.entry.data[CONF_BATTERY_SOC])
        self._battery_full = update_battery_full_hysteresis(soc, self._battery_full)
        if not self.decision.valid or (self.decision.requested_grid_setpoint or 0) > 0:
            self.ev_decision = EVControlDecision(
                valid=True,
                mode=EV_MODE_BLOCKED,
                reason="Battery grid charging blocks PV EV charging",
                strategy=EV_STRATEGY_PV,
                battery_full=self._battery_full,
                requested_current=EV_PAUSE_CURRENT,
            )
            return

        phase_count = self._phase_count(str(options[CONF_EV_PHASE_MODE]))
        battery_power = self._power_state(self.entry.data[CONF_BATTERY_POWER])
        if not bool(
            options.get(
                CONF_BATTERY_CHARGE_POSITIVE,
                DEFAULT_BATTERY_CHARGE_POSITIVE,
            )
        ):
            battery_power = -battery_power
        max_current = float(options.get(CONF_EV_MAX_CURRENT, DEFAULT_EV_MAX_CURRENT))
        voltage = self._numeric_state(str(options[CONF_EV_VOLTAGE]))
        priority = float(options.get(CONF_EV_PRIORITY, DEFAULT_EV_PRIORITY))
        grid_export = 0.0
        grid_power_entity = options.get(CONF_GRID_POWER)
        if self._battery_full and isinstance(grid_power_entity, str):
            try:
                grid_export = min(0.0, self._power_state(grid_power_entity))
            except ValueError:
                _LOGGER.debug(
                    "Grid export is unavailable while the home battery is full"
                )
        raw = calculate_ev_pv_decision(
            ev_power=self._power_state(str(options[CONF_EV_POWER])),
            battery_power=battery_power,
            grid_power=grid_export,
            voltage=voltage,
            phase_count=phase_count,
            priority=priority,
            max_current=max_current,
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
            voltage=voltage,
            phase_count=phase_count,
            priority=priority,
            max_current=max_current,
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
        feedback_entity = options.get(CONF_EV_CURRENT_FEEDBACK)
        measured_current = self._current_state(
            str(feedback_entity or options[CONF_EV_CURRENT_LIMIT])
        )
        # The current-limit number is a command and can read back a rounded,
        # stale value. Only a configured feedback sensor represents measured current.
        current = (
            measured_current
            if feedback_entity or self.last_applied_ev_current is None
            else self.last_applied_ev_current
        )
        requested, control_mode, reason = self._ev_requested_current(
            current=current,
            target=target,
            target_median=target_median,
            max_current=max_current,
            now=now,
        )
        self.ev_decision = replace(
            smoothed,
            mode=control_mode,
            reason=reason,
            requested_current=requested,
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
                    max(EV_MIN_CURRENT, current - EV_PV_CURRENT_STEP),
                ),
                EV_MODE_STOP_DELAY,
                "Temporary PV shortage is buffered",
            )

        self._ev_stop_started = None
        bounded = min(max_current, max(EV_MIN_CURRENT, target))
        if bounded >= current + EV_CURRENT_DEADBAND:
            requested = round(min(max_current, current + EV_PV_CURRENT_STEP), 2)
        elif bounded <= current - EV_CURRENT_DEADBAND:
            requested = round(
                min(
                    max_current,
                    max(EV_MIN_CURRENT, current - EV_PV_CURRENT_STEP),
                ),
                2,
            )
        else:
            requested = current
        return requested, EV_MODE_CHARGING, "EV current follows available PV power"

    @staticmethod
    def _departure_requested_current(*, current: float, target: float) -> float:
        """Ramp departure charging to avoid repeated large EV current changes."""
        if target <= EV_PAUSE_CURRENT:
            return EV_PAUSE_CURRENT
        if current < EV_MIN_CURRENT:
            return EV_MIN_CURRENT
        if target >= current + EV_CURRENT_DEADBAND:
            return round(min(target, current + EV_DEPARTURE_CURRENT_STEP), 2)
        if target <= current - EV_CURRENT_DEADBAND:
            return round(max(EV_MIN_CURRENT, current - EV_DEPARTURE_CURRENT_STEP), 2)
        return round(current, 2)

    async def _async_apply_ev_decision(self) -> None:
        """Optionally apply the calculated EV current."""
        requested = self.ev_decision.requested_current
        if not self._ev_actuation_enabled:
            if self._ev_requires_pause:
                try:
                    await self._async_write_ev_current(EV_PAUSE_CURRENT, force=True)
                    self._last_ev_strategy = EV_STRATEGY_NONE
                except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
                    self.last_ev_actuation_error = str(err)
            else:
                self.last_ev_actuation_error = None
                self._last_ev_strategy = self.ev_decision.strategy
            return

        if requested is None:
            if self._ev_requires_pause:
                requested = EV_PAUSE_CURRENT
            else:
                self.last_ev_actuation_error = None
                self._last_ev_strategy = self.ev_decision.strategy
                return

        try:
            await self._async_write_ev_current(
                requested,
                force=(
                    not self.ev_decision.valid
                    or self.ev_decision.strategy != self._last_ev_strategy
                    or requested <= EV_PAUSE_CURRENT
                ),
            )
            self._last_ev_strategy = self.ev_decision.strategy
        except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
            self.last_ev_actuation_error = str(err)
            _LOGGER.error("Unable to apply GridPilot EV current: %s", err)

    async def _async_apply_soc_load_decision(self) -> None:
        """Turn flexible loads on and off using SOC hysteresis."""
        if not self._soc_load_actuation_enabled:
            self.last_soc_load_actuation_error = None
            return
        entities = self.entry.options.get(CONF_SOC_LOAD_ENTITIES, [])
        if not entities:
            self.last_soc_load_actuation_error = None
            return
        if not isinstance(entities, list) or not all(
            isinstance(entity_id, str) for entity_id in entities
        ):
            self.last_soc_load_actuation_error = "SOC load entities are invalid"
            return
        if unsupported := [
            entity_id
            for entity_id in entities
            if entity_id.partition(".")[0] not in SOC_LOAD_DOMAINS
        ]:
            self.last_soc_load_actuation_error = (
                f"Unsupported SOC load entities: {', '.join(unsupported)}"
            )
            return

        try:
            soc = self._numeric_state(self.entry.data[CONF_BATTERY_SOC])
            on_threshold = float(
                self.entry.options.get(
                    CONF_SOC_LOAD_ON_THRESHOLD, DEFAULT_SOC_LOAD_ON_THRESHOLD
                )
            )
            off_threshold = float(
                self.entry.options.get(
                    CONF_SOC_LOAD_OFF_THRESHOLD, DEFAULT_SOC_LOAD_OFF_THRESHOLD
                )
            )
            if off_threshold > on_threshold:
                raise ValueError(
                    "SOC load off threshold must not exceed on threshold"
                )
            desired_on = (
                True
                if soc >= on_threshold
                else False
                if soc <= off_threshold
                else None
            )
            if desired_on is None:
                self.last_soc_load_actuation_error = None
                return
            targets = [
                entity_id
                for entity_id in entities
                if (state := self.hass.states.get(entity_id)) is not None
                and (state.state != "off") != desired_on
            ]
            if not targets:
                self.last_soc_load_actuation_error = None
                return
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on" if desired_on else "turn_off",
                {ATTR_ENTITY_ID: targets},
                blocking=True,
            )
            self.last_soc_load_actuation_error = None
        except (HomeAssistantError, KeyError, TypeError, ValueError) as err:
            self.last_soc_load_actuation_error = str(err)
            _LOGGER.error("Unable to apply GridPilot SOC load control: %s", err)

    async def _async_write_ev_current(
        self, requested: float, *, force: bool = False
    ) -> None:
        """Validate and write one EV current through Home Assistant."""
        entity_id = self._ev_current_limit_entity
        if not isinstance(entity_id, str):
            raise ValueError("EV current limit is not configured")
        state = self.hass.states.get(entity_id)
        was_unavailable = self._ev_current_limit_unavailable is True
        self._log_ev_current_limit_availability(state)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"EV current limit is unavailable: {entity_id}")
        if state.attributes.get("unit_of_measurement") != "A":
            raise ValueError(f"EV current limit is not measured in A: {entity_id}")
        if "min" not in state.attributes or "max" not in state.attributes:
            raise ValueError(f"EV current limit has no numeric limits: {entity_id}")

        current = float(state.state)
        if (
            was_unavailable
            and self.last_applied_ev_current is not None
            and not math.isclose(
                current, self.last_applied_ev_current, abs_tol=0.05
            )
        ):
            _LOGGER.warning(
                "GridPilot restoring last EV current after recovery: entity=%s "
                "recovered_state=%.2f last_applied=%.2f",
                entity_id,
                current,
                self.last_applied_ev_current,
            )
            requested = self.last_applied_ev_current
        minimum = float(state.attributes["min"])
        maximum = float(state.attributes["max"])
        if not minimum <= requested <= maximum:
            raise ValueError(
                f"EV current {requested} A is outside {minimum}..{maximum} A"
            )
        if math.isclose(current, requested, abs_tol=0.05):
            self.last_applied_ev_current = requested
            self._persist_last_safe_ev_current(requested)
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
        _LOGGER.debug(
            "GridPilot EV current limit write: entity=%s requested=%.2f previous=%.2f "
            "strategy=%s reason=%s force=%s",
            entity_id,
            requested,
            current,
            self.ev_decision.strategy,
            self.ev_decision.reason,
            force,
        )
        self.last_applied_ev_current = requested
        self._persist_last_safe_ev_current(requested)
        self.last_ev_actuation_error = None
        self._last_ev_write_monotonic = now
        self._ev_requires_pause = requested > EV_PAUSE_CURRENT

    def _persist_last_safe_ev_current(self, current: float) -> None:
        """Persist a charge-capable EV current for stale departure SOC fallback."""
        if current < EV_MIN_CURRENT or math.isclose(
            current, self._last_safe_ev_current or 0.0, abs_tol=0.05
        ):
            return
        self._last_safe_ev_current = current
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, CONF_EV_LAST_SAFE_CURRENT: current},
        )

    def _validate_ev_actuator(self) -> None:
        """Ensure the EV actuator supports both pause and configured maximum."""
        entity_id = self._ev_current_limit_entity
        if not isinstance(entity_id, str):
            raise ValueError("EV current limit is not configured")
        state = self._input_state(entity_id)
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
        state = self._input_state(entity_id)
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
        self._ev_restart_until = None

    async def async_shutdown(self) -> bool:
        """Return active battery and EV actuators to neutral setpoints."""
        self._cancel_pending_refresh()
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
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Entity is unavailable: {entity_id}")
        value = float(state.state)
        if not math.isfinite(value):
            raise ValueError(f"Entity is not numeric: {entity_id}")
        return value

    def _update_calculated_ev_soc(self) -> None:
        """Calculate EV SOC from the last reported SOC and charged energy."""
        options = self.entry.options
        soc_entity = options.get(CONF_EV_VEHICLE_SOC)
        energy_entity = options.get(CONF_EV_CHARGE_ENERGY)
        self._calculated_ev_soc = None
        if not isinstance(soc_entity, str) or not isinstance(energy_entity, str):
            self._ev_soc_error = "EV SOC calculation is not configured"
            return

        try:
            charged_energy = self._energy_state(energy_entity)
        except ValueError as err:
            self._ev_soc_error = str(err)
            return

        soc_state = self._input_state(soc_entity)
        if soc_state is not None and soc_state.state not in {"unknown", "unavailable"}:
            try:
                measured_soc = self._numeric_state(soc_entity)
                updated = soc_state.last_updated.timestamp()
                if (
                    self._ev_soc_anchor_updated is None
                    or updated > self._ev_soc_anchor_updated
                ):
                    self._last_measured_ev_soc = measured_soc
                    self._ev_soc_anchor_soc = measured_soc
                    self._ev_soc_anchor_energy = charged_energy
                    self._ev_soc_anchor_updated = updated
                    self._persist_ev_soc_anchor()
            except ValueError:
                pass

        if self._ev_soc_anchor_soc is None or self._ev_soc_anchor_energy is None:
            self._ev_soc_error = "No measured EV SOC is available to anchor calculation"
            return
        if charged_energy < self._ev_soc_anchor_energy:
            self._ev_soc_error = "EV charged-energy meter was reset"
            return

        capacity = float(
            options.get(CONF_EV_BATTERY_CAPACITY, DEFAULT_EV_BATTERY_CAPACITY)
        )
        if not math.isfinite(capacity) or capacity <= 0:
            self._ev_soc_error = "EV battery capacity is invalid"
            return
        charged_since_anchor = charged_energy - self._ev_soc_anchor_energy
        self._calculated_ev_soc = round(
            min(
                100.0,
                max(
                    0.0,
                    self._ev_soc_anchor_soc
                    + charged_since_anchor * EV_CHARGING_EFFICIENCY / capacity * 100,
                ),
            ),
            2,
        )
        self._ev_soc_error = ""

    def _persist_ev_soc_anchor(self) -> None:
        """Persist the most recent measured SOC anchor across restarts."""
        assert self._ev_soc_anchor_soc is not None
        assert self._ev_soc_anchor_energy is not None
        assert self._ev_soc_anchor_updated is not None
        self._skip_next_options_reload += 1
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={
                **self.entry.options,
                CONF_EV_SOC_CALCULATION: {
                    "soc": self._ev_soc_anchor_soc,
                    "energy": self._ev_soc_anchor_energy,
                    "updated": self._ev_soc_anchor_updated,
                },
            },
        )

    def _current_state(self, entity_id: str) -> float:
        """Return one finite current state measured in amperes."""
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Current entity is unavailable: {entity_id}")
        if state.attributes.get("unit_of_measurement") != "A":
            raise ValueError(f"Current entity is not measured in A: {entity_id}")
        value = float(state.state)
        if not math.isfinite(value):
            raise ValueError(f"Current entity is not numeric: {entity_id}")
        return value

    def _duration_state(self, entity_id: str) -> float:
        """Return one finite duration measured in seconds."""
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Duration entity is unavailable: {entity_id}")
        if state.attributes.get("unit_of_measurement") != "s":
            raise ValueError(f"Duration entity is not measured in s: {entity_id}")
        value = float(state.state)
        if not math.isfinite(value):
            raise ValueError(f"Duration entity is not numeric: {entity_id}")
        return value

    def _seconds_until_target(self, entity_id: str) -> float:
        """Return time until the configured deadline, rolling its time forward daily."""
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Target time is unavailable: {entity_id}")
        now = dt_util.now()
        if not state.attributes.get("has_date", True):
            try:
                target = now.replace(
                    hour=int(state.attributes["hour"]),
                    minute=int(state.attributes["minute"]),
                    second=int(state.attributes["second"]),
                    microsecond=0,
                )
            except (KeyError, TypeError, ValueError) as err:
                raise ValueError(f"Target time is invalid: {entity_id}") from err
        else:
            timestamp = float(state.attributes.get("timestamp", math.nan))
            if not math.isfinite(timestamp):
                raise ValueError(f"Target time has no timestamp: {entity_id}")
            target = dt_util.as_local(dt_util.utc_from_timestamp(timestamp))
        while target <= now:
            target += timedelta(days=1)
        return (dt_util.as_utc(target) - dt_util.as_utc(now)).total_seconds()

    def _seconds_until_departure(self) -> float:
        """Return seconds until the configured daily GridPilot departure time."""
        value = str(
            self.entry.options.get(CONF_EV_DEPARTURE_TIME, DEFAULT_EV_DEPARTURE_TIME)
        )
        departure = dt_util.parse_time(value)
        if departure is None:
            raise ValueError("Configured departure time is invalid")
        now = dt_util.now()
        target = now.replace(
            hour=departure.hour,
            minute=departure.minute,
            second=departure.second,
            microsecond=0,
        )
        if target <= now:
            target += timedelta(days=1)
        return (dt_util.as_utc(target) - dt_util.as_utc(now)).total_seconds()

    def _power_state(self, entity_id: str) -> float:
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Power entity is unavailable: {entity_id}")
        return normalize_power(
            float(state.state), state.attributes.get("unit_of_measurement")
        )

    def _energy_state(self, entity_id: str) -> float:
        """Return one finite energy state measured in kWh."""
        state = self._input_state(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"Energy entity is unavailable: {entity_id}")
        unit = state.attributes.get("unit_of_measurement")
        if unit not in {"Wh", "kWh"}:
            raise ValueError(f"Energy entity is not measured in Wh or kWh: {entity_id}")
        value = float(state.state)
        if not math.isfinite(value):
            raise ValueError(f"Energy entity is not numeric: {entity_id}")
        return value / 1000 if unit == "Wh" else value

    def _input_state(self, entity_id: str) -> State | None:
        """Return a state from the active calculation snapshot when available."""
        if self._input_snapshot is not None and entity_id in self._input_snapshot:
            return self._input_snapshot[entity_id]
        return self.hass.states.get(entity_id)

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
    def calculated_ev_soc(self) -> float | None:
        """Return the SOC used by GridPilot's EV planner."""
        return self._calculated_ev_soc

    @property
    def last_measured_ev_soc(self) -> float | None:
        """Return the most recent SOC reported by the vehicle."""
        return self._last_measured_ev_soc

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
                "strategy": self.ev_decision.strategy,
                "mode": self.ev_decision.mode,
                "reason": self.ev_decision.reason,
                "battery_full": self.ev_decision.battery_full,
                "available_pv_power": self.ev_decision.available_pv_power,
                "allocated_ev_power": self.ev_decision.allocated_ev_power,
                "target_current": self.ev_decision.target_current,
                "requested_current": self.ev_decision.requested_current,
                "phase_count": self.ev_decision.phase_count,
            },
            "ev_soc_calculation": {
                "calculated_soc": self.calculated_ev_soc,
                "last_measured_soc": self.last_measured_ev_soc,
                "error": self._ev_soc_error or None,
            },
            "ev_actuation": {
                "enabled": self.ev_actuation_enabled,
                "healthy": self.ev_actuation_healthy,
                "last_applied_current": self.last_applied_ev_current,
                "last_error": self.last_ev_actuation_error,
                "pause_pending": self._ev_requires_pause,
            },
            "soc_load_actuation": {
                "enabled": self._soc_load_actuation_enabled,
                "entities": self.entry.options.get(CONF_SOC_LOAD_ENTITIES, []),
                "last_error": self.last_soc_load_actuation_error,
            },
            "input_coordination": {
                "settle_delay_seconds": INPUT_SETTLE_DELAY.total_seconds(),
                "maximum_delay_seconds": INPUT_MAX_SETTLE_DELAY.total_seconds(),
                "refresh_pending": self._pending_refresh_task is not None,
                "tracked_entities": len(self._tracked_source_entities),
            },
            "shadow_mode": not self.actuation_enabled,
            "ev_shadow_mode": not self.ev_actuation_enabled,
        }
