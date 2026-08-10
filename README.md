# GridPilot

GridPilot is a Home Assistant energy orchestration integration for batteries,
solar production and EV charging. It combines a safe calculation engine with a
compact battery flow dashboard card.

## Current status

Version `0.1.3` is a public preview. It operates permanently in shadow mode:
GridPilot reads configured entities and publishes its calculated battery grid
setpoint, but it never writes to an inverter or charger.

## Initial features

- UI-only configuration through a Home Assistant config flow.
- Generic entity mapping with a Victron-oriented preset.
- Integration-owned grid-power and battery-curve options without helpers.
- Calculated grid setpoint and operating-mode sensors.
- Measurement-validity binary sensor.
- Bundled `custom:gridpilot-card` frontend card.
- Dutch and English translations.

## Manual development installation

Copy `custom_components/gridpilot` into the Home Assistant configuration
directory under `custom_components`, restart Home Assistant, and add GridPilot
from **Settings > Devices & services**.

Do not disable an existing controller yet. GridPilot `0.1.x` is intended to run
alongside it for comparison.

## Planned releases

- `0.2`: opt-in battery actuation and Victron preset.
- `0.3`: PV surplus and EV current control.
- `0.4`: battery-to-EV and manual charging modes.
- `1.0`: stable migration and public HACS release.

## License

MIT
