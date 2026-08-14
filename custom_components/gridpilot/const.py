"""Constants for GridPilot."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "gridpilot"
NAME: Final = "GridPilot"
VERSION: Final = "1.2.0"

PLATFORMS: Final = ["sensor", "binary_sensor", "number"]
UPDATE_INTERVAL: Final = timedelta(minutes=1)
MIN_ACTUATION_INTERVAL: Final = timedelta(seconds=10)
EV_UPDATE_INTERVAL: Final = timedelta(seconds=4)
EV_POWER_MEDIAN_WINDOW: Final = timedelta(seconds=45)
EV_CURRENT_MEDIAN_WINDOW: Final = timedelta(minutes=2)
EV_STOP_DELAY: Final = timedelta(minutes=5)
EV_RESTART_DELAY: Final = timedelta(minutes=10)

CONF_PROFILE: Final = "profile"
CONF_BATTERY_SOC: Final = "battery_soc"
CONF_BATTERY_POWER: Final = "battery_power"
CONF_BATTERY_ENERGY: Final = "battery_energy"
CONF_BATTERY_CHARGE_ENERGY: Final = "battery_charge_energy"
CONF_BATTERY_DISCHARGE_ENERGY: Final = "battery_discharge_energy"
CONF_GRID_SETPOINT: Final = "grid_setpoint"
CONF_MAX_GRID_POWER: Final = "max_grid_power"
CONF_HOME_LOAD: Final = "home_load"
CONF_HOME_LOAD_L1: Final = "home_load_l1"
CONF_HOME_LOAD_L2: Final = "home_load_l2"
CONF_HOME_LOAD_L3: Final = "home_load_l3"

CONF_MINIMUM_SOC: Final = "minimum_soc"
CONF_CHARGE_SOC: Final = "charge_soc"
CONF_NORMAL_SOC: Final = "normal_soc"
CONF_ENABLE_ACTUATION: Final = "enable_actuation"
CONF_GRID_POWER: Final = "grid_power"
CONF_EV_POWER: Final = "ev_power"
CONF_EV_VEHICLE_SOC: Final = "ev_vehicle_soc"
CONF_EV_CONNECTION_STATE: Final = "ev_connection_state"
CONF_EV_CURRENT_LIMIT: Final = "ev_current_limit"
CONF_EV_CURRENT_FEEDBACK: Final = "ev_current_feedback"
CONF_EV_VOLTAGE: Final = "ev_voltage"
CONF_EV_PHASE_MODE: Final = "ev_phase_mode"
CONF_GRIDPILOT_EV_MODE: Final = "gridpilot_ev_mode"
CONF_EV_OVERRIDE: Final = "ev_override"
CONF_EV_MANUAL_CURRENT: Final = "ev_manual_current"
CONF_EV_BATTERY_SOC: Final = "ev_battery_soc"
CONF_EV_BATTERY_MIN_SOC: Final = "ev_battery_min_soc"
CONF_EV_BATTERY_TIME_TO_GO: Final = "ev_battery_time_to_go"
CONF_EV_BATTERY_TARGET_TIME: Final = "ev_battery_target_time"
CONF_BATTERY_CHARGE_POSITIVE: Final = "battery_charge_positive"
CONF_EV_PRIORITY: Final = "ev_priority"
CONF_EV_MAX_CURRENT: Final = "ev_max_current"
CONF_PV_SAFETY_MARGIN: Final = "pv_safety_margin"
CONF_ENABLE_EV_ACTUATION: Final = "enable_ev_actuation"
CONF_SOC_LOAD_ENTITIES: Final = "soc_load_entities"
CONF_SOC_LOAD_ON_THRESHOLD: Final = "soc_load_on_threshold"
CONF_SOC_LOAD_OFF_THRESHOLD: Final = "soc_load_off_threshold"
CONF_ENABLE_SOC_LOAD_ACTUATION: Final = "enable_soc_load_actuation"
CONF_EV_DEPARTURE_TIME: Final = "ev_departure_time"
CONF_EV_DEPARTURE_TARGET_SOC: Final = "ev_departure_target_soc"
CONF_EV_BATTERY_CAPACITY: Final = "ev_battery_capacity"
CONF_EV_CHARGE_ENERGY: Final = "ev_charge_energy"
CONF_EV_DISCHARGE_ENERGY: Final = "ev_discharge_energy"
CONF_CAPACITY_CALIBRATION: Final = "capacity_calibration"
CAPACITY_MIN_SOC_DELTA: Final = 5.0
CAPACITY_MIN_ENERGY_DELTA: Final = 1.0
CAPACITY_SMOOTHING: Final = 0.25

DEFAULT_CHARGE_SOC: Final = 15.0
SOC_THRESHOLD_OFFSET: Final = 5.0
DEFAULT_MAX_GRID_POWER: Final = 2_900.0
DEFAULT_ENABLE_ACTUATION: Final = False
DEFAULT_ENABLE_EV_ACTUATION: Final = False
DEFAULT_SOC_LOAD_ON_THRESHOLD: Final = 90.0
DEFAULT_SOC_LOAD_OFF_THRESHOLD: Final = 30.0
DEFAULT_ENABLE_SOC_LOAD_ACTUATION: Final = False
SOC_LOAD_DOMAINS: Final = frozenset(
    {"climate", "fan", "humidifier", "light", "media_player", "switch", "water_heater"}
)
DEFAULT_BATTERY_CHARGE_POSITIVE: Final = True
DEFAULT_EV_PV_MODE: Final = "PV laden"
DEFAULT_EV_MANUAL_MODE: Final = "Manueel"
DEFAULT_EV_BATTERY_MODE: Final = "Thuisbatterij naar EV"
DEFAULT_EV_DEPARTURE_MODE: Final = "Vertrektijd"
DEFAULT_EV_DISCONNECTED_STATE: Final = "Available"
DEFAULT_EV_OFF_MODE: Final = "Uit"
DEFAULT_EV_MODE: Final = DEFAULT_EV_PV_MODE
EV_MODE_OPTIONS: Final = [
    DEFAULT_EV_OFF_MODE,
    DEFAULT_EV_PV_MODE,
    DEFAULT_EV_MANUAL_MODE,
    DEFAULT_EV_BATTERY_MODE,
    DEFAULT_EV_DEPARTURE_MODE,
]
DEFAULT_EV_PRIORITY: Final = 50.0
DEFAULT_EV_MAX_CURRENT: Final = 16.0
DEFAULT_PV_SAFETY_MARGIN: Final = 0.0
DEFAULT_EV_DEPARTURE_TARGET_SOC: Final = 80.0
DEFAULT_EV_BATTERY_CAPACITY: Final = 75.0
DEFAULT_EV_DEPARTURE_TIME: Final = "08:00:00"
EV_CHARGING_EFFICIENCY: Final = 0.95

EV_PAUSE_CURRENT: Final = 5.0
EV_MIN_CURRENT: Final = 6.0
EV_START_CURRENT: Final = 7.0
EV_STOP_CURRENT: Final = 5.5
EV_CURRENT_STEP: Final = 0.1
EV_DEPARTURE_CURRENT_STEP: Final = 0.5
DEPARTURE_SETPOINT_STEP: Final = 250.0
DEPARTURE_BATTERY_POWER_DEADBAND: Final = 150.0
DEPARTURE_SETPOINT_INTERVAL: Final = timedelta(seconds=10)
EV_CURRENT_DEADBAND: Final = 0.3
BATTERY_FULL_SOC: Final = 98.0
BATTERY_FULL_RELEASE_SOC: Final = 97.0
EV_BATTERY_GRID_IMPORT_LIMIT: Final = 150.0
EV_BATTERY_MIN_TOLERANCE: Final = 600.0

EV_STRATEGY_NONE: Final = "none"
EV_STRATEGY_PV: Final = "pv"
EV_STRATEGY_MANUAL: Final = "manual"
EV_STRATEGY_BATTERY_TO_EV: Final = "battery_to_ev"
EV_STRATEGY_DEPARTURE: Final = "departure"
EV_STRATEGIES: Final = [
    EV_STRATEGY_NONE,
    EV_STRATEGY_PV,
    EV_STRATEGY_MANUAL,
    EV_STRATEGY_BATTERY_TO_EV,
    EV_STRATEGY_DEPARTURE,
]

PROFILE_GENERIC: Final = "generic"
PROFILE_VICTRON: Final = "victron"

MODE_UNAVAILABLE: Final = "unavailable"
MODE_MAX_CHARGING: Final = "max_charging"
MODE_CHARGING: Final = "charging"
MODE_NEUTRAL: Final = "neutral"
MODE_TAPERING: Final = "tapering"
MODE_NORMAL: Final = "normal"
MODES: Final = [
    MODE_UNAVAILABLE,
    MODE_MAX_CHARGING,
    MODE_CHARGING,
    MODE_NEUTRAL,
    MODE_TAPERING,
    MODE_NORMAL,
]

EV_MODE_UNAVAILABLE: Final = "unavailable"
EV_MODE_INACTIVE: Final = "inactive"
EV_MODE_DISCONNECTED: Final = "disconnected"
EV_MODE_BLOCKED: Final = "blocked"
EV_MODE_WAITING: Final = "waiting"
EV_MODE_CHARGING: Final = "charging"
EV_MODE_STOP_DELAY: Final = "stop_delay"
EV_MODE_RESTART_BLOCKED: Final = "restart_blocked"
EV_CONTROL_MODES: Final = [
    EV_MODE_UNAVAILABLE,
    EV_MODE_INACTIVE,
    EV_MODE_DISCONNECTED,
    EV_MODE_BLOCKED,
    EV_MODE_WAITING,
    EV_MODE_CHARGING,
    EV_MODE_STOP_DELAY,
    EV_MODE_RESTART_BLOCKED,
]
