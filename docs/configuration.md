# Configuration

GridPilot is configured entirely from Home Assistant's integration UI.

Version 0.1 requires a battery SOC sensor, battery power sensor, writable grid
setpoint number and either one total home-load sensor or all three phase
sensors.

Maximum grid import, the three SOC thresholds and minimum charging power are
stored persistently in the GridPilot config-entry options. They can be changed
from **Settings > Devices & services > GridPilot > Configure**. GridPilot does
not create Home Assistant helpers for these values.

The first release is permanently read-only. Selecting a writable setpoint lets
GridPilot validate the future actuator mapping, but no service call is made.
