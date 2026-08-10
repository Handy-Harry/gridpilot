# Migration

Do not disable an existing energy controller when installing GridPilot 0.1.
Compare `sensor.gridpilot_calculated_grid_setpoint` with the active controller
for several days. Actuation will be introduced as a separate opt-in feature in
0.2.
