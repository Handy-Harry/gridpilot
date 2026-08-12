# GridPilot v1.0.0

GridPilot v1.0.0 is the first stable release. The configured charging-mode
select is the sole EV strategy selector for off, PV, manual and battery-to-EV
operation. Config-entry migration v6 removes the legacy override mapping while
preserving active-control settings and all entity mappings.

Battery and EV actuation remain independently opt-in. Invalid battery inputs
neutralize the grid setpoint, while invalid or reserve-limited EV control uses
the configured safe 5 A pause value.

Validated with the full Python test suite, Ruff, translation consistency,
frontend syntax, HACS validation and hassfest.
