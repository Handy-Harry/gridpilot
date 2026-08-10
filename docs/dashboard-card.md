# GridPilot card

The integration loads `custom:gridpilot-card` automatically.

```yaml
type: custom:gridpilot-card
entity: sensor.battery_soc
name: Home battery
status_entity: sensor.battery_state
charge_state: charging
discharge_state: discharging
power_entity: sensor.battery_power
minimum_entity: number.minimum_soc
charge_below: 15
normal_above: 20
setpoint_entity: sensor.gridpilot_calculated_grid_setpoint
```

For an EV target zone, configure `target_entity` instead of the battery control
range options.
