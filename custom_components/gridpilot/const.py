"""Constants for GridPilot."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "gridpilot"
NAME: Final = "GridPilot"
VERSION: Final = "0.1.0"

PLATFORMS: Final = ["sensor", "binary_sensor"]
UPDATE_INTERVAL: Final = timedelta(minutes=1)

CONF_PROFILE: Final = "profile"
CONF_BATTERY_SOC: Final = "battery_soc"
CONF_BATTERY_POWER: Final = "battery_power"
CONF_GRID_SETPOINT: Final = "grid_setpoint"
CONF_MAX_GRID_POWER: Final = "max_grid_power"
CONF_HOME_LOAD: Final = "home_load"
CONF_HOME_LOAD_L1: Final = "home_load_l1"
CONF_HOME_LOAD_L2: Final = "home_load_l2"
CONF_HOME_LOAD_L3: Final = "home_load_l3"

CONF_MINIMUM_SOC: Final = "minimum_soc"
CONF_CHARGE_SOC: Final = "charge_soc"
CONF_NORMAL_SOC: Final = "normal_soc"
CONF_MINIMUM_CHARGE_POWER: Final = "minimum_charge_power"

DEFAULT_MINIMUM_SOC: Final = 10.0
DEFAULT_CHARGE_SOC: Final = 15.0
DEFAULT_NORMAL_SOC: Final = 20.0
DEFAULT_MINIMUM_CHARGE_POWER: Final = 300.0

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
