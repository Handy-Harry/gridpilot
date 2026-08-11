# Configuration

GridPilot is configured entirely from Home Assistant's integration UI.

GridPilot requires a battery SOC sensor, battery power sensor, writable grid
setpoint number and either one total home-load sensor or all three phase
sensors.

Maximum grid import, the three SOC thresholds and minimum charging power are
stored persistently in the GridPilot config-entry options. They can be changed
from **Settings > Devices & services > GridPilot > Configure**. GridPilot does
not create Home Assistant helpers for these values.

Version 0.2 adds optional battery actuation. It is disabled by default and must
only be enabled after disabling every other automation or integration that
writes to the configured grid setpoint.
