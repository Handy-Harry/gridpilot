# Battery control curve

The battery calculation uses three SOC thresholds:

- 10%: maximum configured grid import.
- 15%: grid import equals the current home load.
- 20%: calculated grid setpoint reaches zero.

Between thresholds the requested power changes linearly and is always capped by
the configured maximum grid power.

Version 0.2 remains in shadow mode by default. Active control can be enabled
explicitly from the integration options after every other controller writing to
the same setpoint has been disabled. GridPilot writes only changed setpoints. If
measurements become invalid, or the active controller unloads, it requests the
neutral 0 W setpoint as a fail-safe.
