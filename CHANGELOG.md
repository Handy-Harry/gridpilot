# Changelog

## 1.3.4 - 2026-08-15

- Configure SOC-controlled devices individually with their own on and off
  thresholds, and migrate existing shared thresholds safely.
- Show each device's SOC switching thresholds correctly on the GridPilot dashboard.
- Improve GridPilot's battery and EV energy configuration, dashboard information,
  translations, and test coverage.

## 1.1.3 - 2026-08-12

- Preserve the measured EV charging current while changing PV priority or switching
  charging strategies; write the 5 A stop value only for an explicit stop decision.

## 1.3.0 - 2026-08-14

- Add departure-time EV charging with a target SOC, planned-current control, and
  deadline feedback.
- Add learned usable-capacity calibration and energy sensors for the home battery
  and EV, with configured capacity fallbacks.
- Extend the GridPilot dashboard with EV departure planning and battery-energy
  information.

## 1.1.2 - 2026-08-12

- Rename the EV charging mode label to `Thuisbatterij naar EV` and use `Automatisch` in the dashboard selector.
- Translate dashboard strategy, operating-mode and control-reason labels for Dutch users.
- Replace remaining English entity-type terms in the Dutch configuration descriptions.

## 1.1.1 - 2026-08-12

- Add correctly sized local 1x and 2x GridPilot icon and logo assets.
- Keep the EV-battery card at the top of the EV charging dashboard section.
- Restore the derived battery-curve thresholds on the home-battery card.

## 1.1.0 - 2026-08-12

- Add an installation-managed GridPilot dashboard with PV-priority, manual EV controls and a battery-to-EV discharge limit.
- Add an optional vehicle-SOC mapping for the dashboard EV-battery card.
- Derive card charging and discharging activity from power when no explicit status mapping is available.

## 1.0.0 - 2026-08-12

- Make the charging-mode dropdown the sole EV strategy selector.
- Add a configurable `Thuisbatterij naar auto` mode value.
- Remove the legacy battery-to-EV override mapping through config-entry migration v6.
- Keep active battery and EV actuation opt-in with safe neutral and 5 A fallbacks.
- Validate the stable release with controller, migration, config-flow and fail-safe tests.

## 0.4.1 - 2026-08-11

- Make the laadmodus dropdown authoritative over the battery-to-EV override.
- Add explicit `Thuisbatterij naar auto` mode selection.
- Validate PV, manual and battery-to-EV mode precedence with controller tests.

## 0.4.0 - 2026-08-11

- Add coordinated PV, manual and battery-to-EV charging strategies using existing UI-managed helpers.
- Add safe 6 A strategy handoff, immediate 5 A pauses and reserve-SOC/time-to-go control.
- Add strategy diagnostics, config-entry migration v5 and legacy override compatibility.
- Validate with 65 tests, Ruff, JSON/translation checks and frontend syntax checks.

## 0.3.0 - 2026-08-11

- Calculate PV surplus and phase-aware EV target current inside GridPilot.
- Add 98/97% battery-full hysteresis, smoothing, ramping and restart protection.
- Add opt-in EV current actuation with a safe 5 A pause setpoint.
- Expose EV decision, health and shadow-mode entities.
- Add configurable battery-power polarity and optional applied-current feedback.
- Validate the EV actuator's safe 5 A pause value before active control.

## 0.2.1 - 2026-08-11

- Replace three configurable SOC thresholds with one full-compensation SOC.
- Derive maximum charging and normal battery operation 5 percentage points below and above it.
- Migrate existing config entries while preserving active-control settings.

## 0.2.0 - 2026-08-11

- Add opt-in battery setpoint actuation, disabled by default.
- Reset the setpoint to 0 W when measurements become invalid or active control unloads.
- Expose actuation health and bounded diagnostics.

## 0.1.11 - 2026-08-11

- Update the GridPilot meter artwork with the supplied v5 design.

## 0.1.10 - 2026-08-11

- Replace the GridPilot integration and repository artwork with the supplied capacity-tariff meter logo.

## 0.1.9 - 2026-08-11

- Remove the brand icon from the GridPilot dashboard card title.

## 0.1.8 - 2026-08-11

- Re-announce the bundled dashboard card whenever GridPilot loads, including after an integration reload.

## 0.1.7 - 2026-08-10

- Replace the smart-meter artwork with the compact 256 px version.

## 0.1.6 - 2026-08-10

- Add the smart-meter brand artwork to the integration, dashboard card and README.

## 0.1.5 - 2026-08-10

- Classify GridPilot as a service so it appears under integrations, not helpers.

## 0.1.4 - 2026-08-10

- Set the maximum grid-import adjustment step to 100 W.

## 0.1.3 - 2026-08-10

- Limit the maximum grid-import setting to 10,000 W.

## 0.1.2 - 2026-08-10

- Store all fixed control parameters in GridPilot config-entry options.
- Remove the maximum grid-power entity requirement from setup.
- Migrate existing maximum grid-power mappings without removing their entities.

## 0.1.1 - 2026-08-10

- Add detailed setup guidance for every configuration and battery-curve field.

## 0.1.0 - 2026-08-10

- Add the initial HACS integration structure.
- Add UI configuration and options flows.
- Add a read-only battery control calculation engine.
- Add diagnostic sensors and the GridPilot dashboard card.
