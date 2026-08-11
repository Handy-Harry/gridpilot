# Migration

Do not disable an existing energy controller when initially installing GridPilot.
Compare `sensor.gridpilot_calculated_grid_setpoint` with the active controller
for several days. In 0.2, disable the existing controller before explicitly
enabling GridPilot actuation from the integration options.

GridPilot 0.1.2 automatically migrates the maximum grid-power value from an
existing entity mapping into its own persistent options. The entity itself is
not removed because other automations may still use it.
