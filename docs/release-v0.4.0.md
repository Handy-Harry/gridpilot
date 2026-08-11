# GridPilot v0.4.0

GridPilot v0.4.0 coordinates PV, manual and battery-to-EV charging through one safe EV actuator owner. It reuses existing UI-managed current, reserve-SOC, time-to-go and target-time helpers, with safe 6 A strategy handoff, immediate 5 A pauses and new strategy diagnostics. EV actuation remains opt-in and disabled by default.

Validated successfully with 65 tests, Ruff, JSON and translation consistency checks, frontend syntax checks and an independent safety review.
