# Battery control curve

The default shadow calculation uses three SOC thresholds:

- 10%: maximum configured grid import.
- 15%: grid import equals the current home load.
- 20%: calculated grid setpoint reaches zero.

Between thresholds the requested power changes linearly and is always capped by
the configured maximum grid-power entity. Version 0.1 only exposes the result as
a sensor.
