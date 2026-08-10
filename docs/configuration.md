# Configuration

GridPilot is configured entirely from Home Assistant's integration UI.

Version 0.1 requires a battery SOC sensor, battery power sensor, writable grid
setpoint number, maximum grid-power entity and either one total home-load
sensor or all three phase sensors.

The first release is permanently read-only. Selecting a writable setpoint lets
GridPilot validate the future actuator mapping, but no service call is made.
