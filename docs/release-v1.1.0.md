# GridPilot v1.1.0

GridPilot now creates and refreshes its own Home Assistant dashboard. The dashboard
includes an EV-priority slider for PV charging, manual current and phase controls,
and a 5%-step home-battery discharge limit for battery-to-EV charging.

The bundled battery card can derive charging and discharging activity from power
when no explicit status mapping is available. A new optional vehicle-SOC mapping
controls the EV-battery card on the dashboard without affecting control safety.

After upgrading, open the GridPilot integration options and select the vehicle SOC
under **EV SOC for dashboard** if you want the EV-battery card to be displayed.
