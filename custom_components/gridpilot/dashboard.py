"""Create the bundled GridPilot dashboard."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.components.lovelace.dashboard import (
    DashboardsCollection,
    LovelaceStorage,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_CHARGE_POSITIVE,
    CONF_BATTERY_POWER,
    CONF_BATTERY_SOC,
    CONF_CHARGE_SOC,
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_VEHICLE_SOC,
    CONF_GRID_SETPOINT,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_CHARGE_SOC,
    DEFAULT_EV_BATTERY_MODE,
    DEFAULT_EV_DEPARTURE_MODE,
    DEFAULT_EV_MANUAL_MODE,
    DEFAULT_EV_PV_MODE,
    DOMAIN,
    SOC_THRESHOLD_OFFSET,
)
from .runtime import GridPilotConfigEntry

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL = "gridpilot-dashboard"
DASHBOARD_TITLE = "GridPilot"
DASHBOARD_ICON = "mdi:home-lightning-bolt"


async def async_ensure_dashboard(
    hass: HomeAssistant, entry: GridPilotConfigEntry
) -> None:
    """Create or refresh the installation-managed GridPilot dashboard."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        return

    if dashboard := lovelace.dashboards.get(DASHBOARD_URL):
        await dashboard.async_save(_dashboard_config(hass, entry))
        return

    collection = DashboardsCollection(hass)
    await collection.async_load()
    if any(item.get("url_path") == DASHBOARD_URL for item in collection.async_items()):
        return

    try:
        item = await collection.async_create_item(
            {
                "url_path": DASHBOARD_URL,
                "title": DASHBOARD_TITLE,
                "icon": DASHBOARD_ICON,
                "show_in_sidebar": True,
                "require_admin": False,
            }
        )
    except (HomeAssistantError, vol.Invalid):
        _LOGGER.exception("Unable to create the GridPilot dashboard")
        return

    dashboard = LovelaceStorage(hass, item)
    lovelace.dashboards[DASHBOARD_URL] = dashboard
    frontend.async_register_built_in_panel(
        hass,
        "lovelace",
        frontend_url_path=DASHBOARD_URL,
        sidebar_title=DASHBOARD_TITLE,
        sidebar_icon=DASHBOARD_ICON,
        require_admin=False,
        config={"mode": MODE_STORAGE},
    )
    await dashboard.async_save(_dashboard_config(hass, entry))


def _gridpilot_entity(
    hass: HomeAssistant, entry: GridPilotConfigEntry, domain: str, suffix: str
) -> str:
    """Resolve a GridPilot entity ID from its stable unique ID."""
    registry = er.async_get(hass)
    return registry.async_get_entity_id(
        domain, DOMAIN, f"{entry.entry_id}_{suffix}"
    ) or f"{domain}.gridpilot_{suffix}"


def _dashboard_config(
    hass: HomeAssistant, entry: GridPilotConfigEntry
) -> dict[str, Any]:
    """Build a dashboard from the configured GridPilot entities."""
    data = entry.data
    calculated_setpoint = _gridpilot_entity(
        hass, entry, "sensor", "calculated_grid_setpoint"
    )
    operating_mode = _gridpilot_entity(hass, entry, "sensor", "operating_mode")
    control_reason = _gridpilot_entity(hass, entry, "sensor", "control_reason")
    measurements_valid = _gridpilot_entity(
        hass, entry, "binary_sensor", "measurements_valid"
    )
    shadow_mode = _gridpilot_entity(hass, entry, "binary_sensor", "shadow_mode")
    actuation_healthy = _gridpilot_entity(
        hass, entry, "binary_sensor", "actuation_healthy"
    )
    home_battery_energy = _gridpilot_entity(
        hass, entry, "sensor", "home_battery_energy"
    )
    home_battery_capacity = _gridpilot_entity(
        hass, entry, "sensor", "home_battery_capacity"
    )
    home_battery_capacity_configured = _gridpilot_entity(
        hass, entry, "number", "home_battery_capacity_configured"
    )
    charge_soc_entity = _gridpilot_entity(hass, entry, "number", "charge_soc")
    preload = _gridpilot_entity(hass, entry, "switch", "preload")
    desired_charge_soc = _gridpilot_entity(
        hass, entry, "sensor", "desired_charge_soc"
    )
    active_charge_soc = _gridpilot_entity(
        hass, entry, "sensor", "active_charge_soc"
    )
    ev_battery_energy = _gridpilot_entity(hass, entry, "sensor", "ev_battery_energy")
    ev_energy_to_target = _gridpilot_entity(
        hass, entry, "sensor", "ev_energy_to_target"
    )
    ev_battery_capacity_learned = _gridpilot_entity(
        hass, entry, "sensor", "ev_battery_capacity_learned"
    )
    soc_load_devices = _gridpilot_entity(hass, entry, "sensor", "soc_load_devices")
    charge_soc = float(entry.options.get(CONF_CHARGE_SOC, DEFAULT_CHARGE_SOC))
    battery_cards: list[dict[str, Any]] = [
        {
            "type": "heading",
            "heading": "Energiebeheer",
            "heading_style": "title",
            "icon": "mdi:home-lightning-bolt",
        },
        {
            "type": "custom:gridpilot-card",
            "name": "Thuisbatterij",
            "entity": data[CONF_BATTERY_SOC],
            "power_entity": data[CONF_BATTERY_POWER],
            "power_charge_positive": entry.options.get(
                CONF_BATTERY_CHARGE_POSITIVE, DEFAULT_BATTERY_CHARGE_POSITIVE
            ),
            "charge_entity": active_charge_soc,
            "target_entity": desired_charge_soc,
            "threshold_offset": SOC_THRESHOLD_OFFSET,
            "minimum_soc": charge_soc - SOC_THRESHOLD_OFFSET,
            "charge_below": charge_soc,
            "normal_above": charge_soc + SOC_THRESHOLD_OFFSET,
            "setpoint_entity": calculated_setpoint,
        },
        {
            "type": "grid",
            "columns": 2,
            "square": False,
            "cards": [
                {
                    "type": "tile",
                    "entity": charge_soc_entity,
                    "name": "Reserve SOC",
                    "icon": "mdi:battery-charging-medium",
                    "features": [{"type": "numeric-input", "style": "slider"}],
                },
                {
                    "type": "vertical-stack",
                    "cards": [
                        {
                            "type": "tile",
                            "entity": desired_charge_soc,
                            "name": "Gewenste SOC",
                            "icon": "mdi:battery-arrow-up",
                        },
                        {
                            "type": "tile",
                            "entity": preload,
                            "name": "Voorladen",
                            "icon": "mdi:battery-clock",
                        },
                    ],
                },
            ],
        },
        {
            "type": "markdown",
            "content": _control_markdown(
                calculated_setpoint,
                data[CONF_GRID_SETPOINT],
                operating_mode,
                control_reason,
                measurements_valid,
                shadow_mode,
                actuation_healthy,
            ),
        },
        {
            "type": "entities",
            "title": "GridPilot energie",
            "entities": [
                home_battery_energy,
                home_battery_capacity,
                home_battery_capacity_configured,
                ev_battery_energy,
                ev_energy_to_target,
                ev_battery_capacity_learned,
            ],
        },
        {"type": "markdown", "content": _soc_load_markdown(soc_load_devices)},
    ]

    ev_cards = _ev_cards(hass, entry)
    sections = [
        {"type": "grid", "cards": battery_cards},
    ]
    if ev_cards:
        sections.append({"type": "grid", "cards": ev_cards})

    return {
        "title": DASHBOARD_TITLE,
        "views": [
            {
                "title": "Overzicht",
                "path": "overzicht",
                "icon": DASHBOARD_ICON,
                "type": "sections",
                "max_columns": 2,
                "sections": sections,
            }
        ],
    }


def _ev_cards(
    hass: HomeAssistant, entry: GridPilotConfigEntry
) -> list[dict[str, Any]]:
    """Build EV cards when EV control is configured."""
    options = entry.options
    ev_mode = _gridpilot_entity(hass, entry, "select", "ev_mode")
    strategy = _gridpilot_entity(hass, entry, "sensor", "ev_strategy")
    operating_mode = _gridpilot_entity(hass, entry, "sensor", "ev_operating_mode")
    reason = _gridpilot_entity(hass, entry, "sensor", "ev_control_reason")
    target_current = _gridpilot_entity(hass, entry, "sensor", "ev_target_current")
    priority = _gridpilot_entity(hass, entry, "number", "ev_priority")
    departure_target_soc = _gridpilot_entity(
        hass, entry, "number", "ev_departure_target_soc"
    )
    battery_capacity = _gridpilot_entity(
        hass, entry, "number", "ev_battery_capacity"
    )
    departure_time = _gridpilot_entity(hass, entry, "time", "ev_departure_time")
    measurements_valid = _gridpilot_entity(
        hass, entry, "binary_sensor", "ev_measurements_valid"
    )
    actuation_healthy = _gridpilot_entity(
        hass, entry, "binary_sensor", "ev_actuation_healthy"
    )

    cards: list[dict[str, Any]] = [
        {
            "type": "heading",
            "heading": "EV laden",
            "heading_style": "title",
            "icon": "mdi:ev-station",
        },
    ]
    if options.get(CONF_EV_VEHICLE_SOC):
        card: dict[str, Any] = {
            "type": "custom:gridpilot-card",
            "name": "EV-batterij",
            "entity": options[CONF_EV_VEHICLE_SOC],
        }
        if options.get(CONF_EV_POWER):
            card["power_entity"] = options[CONF_EV_POWER]
        cards.append(card)

    cards.extend(
        [
        {
            "type": "tile",
            "entity": ev_mode,
            "name": "Laadmodus kiezen",
            "icon": "mdi:ev-station",
            "features": [{"type": "select-options"}],
        },
        {
            "type": "conditional",
            "conditions": [
                {
                    "condition": "state",
                    "entity": ev_mode,
                    "state": DEFAULT_EV_PV_MODE,
                }
            ],
            "card": {
                "type": "tile",
                "entity": priority,
                "name": "PV-prioriteit: thuisbatterij 0% / EV 100%",
                "icon": "mdi:solar-power",
                "features": [{"type": "numeric-input", "style": "slider"}],
            },
        },
        ]
    )
    manual_entities = [
        options.get(CONF_EV_MANUAL_CURRENT),
        options.get(CONF_EV_PHASE_MODE),
    ]
    manual_cards = [
        {
            "type": "tile",
            "entity": entity_id,
            "name": name,
            "icon": icon,
            "features": [feature] if feature else [],
        }
        for entity_id, name, icon, feature in (
            (
                manual_entities[0],
                "Handmatige laadstroom",
                "mdi:current-ac",
                {"type": "numeric-input", "style": "slider"},
            ),
            (
                manual_entities[1],
                "Handmatige fasen",
                "mdi:sine-wave",
                (
                    {"type": "select-options"}
                    if manual_entities[1] and manual_entities[1].startswith("select.")
                    else None
                ),
            ),
        )
        if entity_id
    ]
    if manual_cards:
        cards.append(
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": ev_mode,
                        "state": DEFAULT_EV_MANUAL_MODE,
                    }
                ],
                "card": {
                    "type": "grid",
                    "columns": len(manual_cards),
                    "square": False,
                    "cards": manual_cards,
                },
            }
        )
    if minimum_soc := options.get(CONF_EV_BATTERY_MIN_SOC):
        cards.append(
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": ev_mode,
                        "state": DEFAULT_EV_BATTERY_MODE,
                    }
                ],
                "card": {
                    "type": "tile",
                    "entity": minimum_soc,
                    "name": "Thuisbatterij ontladen tot",
                    "icon": "mdi:battery-low",
                    "features": [
                        {"type": "numeric-input", "style": "slider"}
                    ],
                },
            }
        )
    cards.append(
            {
                "type": "conditional",
                "conditions": [
                    {
                        "condition": "state",
                        "entity": ev_mode,
                        "state": DEFAULT_EV_DEPARTURE_MODE,
                    }
                ],
                "card": {
                    "type": "vertical-stack",
                    "cards": [
                        {
                            "type": "entities",
                            "title": "Vertrektijd laden",
                            "entities": [
                                departure_time,
                                departure_target_soc,
                                battery_capacity,
                            ],
                        },
                        {
                            "type": "markdown",
                            "content": _departure_plan_markdown(
                                operating_mode,
                                reason,
                                target_current,
                                departure_time,
                                departure_target_soc,
                            ),
                        },
                    ],
                },
            }
    )
    cards.extend(
        [
            {
                "type": "entities",
                "title": "EV-regeling",
                "entities": [
                    strategy,
                    operating_mode,
                    target_current,
                    measurements_valid,
                    actuation_healthy,
                ],
            },
            {
                "type": "markdown",
                "content": _ev_markdown(
                    ev_mode,
                    strategy,
                    operating_mode,
                    reason,
                    target_current,
                    measurements_valid,
                    actuation_healthy,
                    options.get(CONF_EV_CURRENT_LIMIT),
                ),
            },
        ]
    )
    return cards


def _control_markdown(
    calculated: str,
    actual: str,
    mode: str,
    reason: str,
    valid: str,
    shadow: str,
    healthy: str,
) -> str:
    """Return the dynamic battery-control explanation."""
    return """### GridPilot regeling
{% set calculated = states('CALCULATED') | float(0) %}
{% set actual = states('ACTUAL') | float(0) %}
{% set difference = actual - calculated %}
{% set mode_labels = {
  'unavailable': 'Niet beschikbaar',
  'max_charging': 'Maximaal bijladen',
  'charging': 'Bijladen',
  'neutral': 'Neutraal',
  'tapering': 'Afbouwen',
  'normal': 'Normaal'
} %}
{% set reason_labels = {
  'SOC is at or above the normal threshold':
    'De SOC ligt op of boven de grens voor normale werking',
  'Grid compensation tapers linearly toward zero':
    'De netcompensatie wordt geleidelijk tot nul afgebouwd',
  'Grid setpoint compensates the home load':
    'Het netsetpoint compenseert het huisverbruik',
  'SOC is at or below the minimum threshold': 'De SOC ligt op of onder de minimumgrens',
   'Charge power rises as SOC approaches the minimum threshold':
    'Het laadvermogen stijgt wanneer de SOC de minimumgrens nadert',
  'Grid covers home load and planned EV charging':
    'Het net dekt het huisverbruik en het geplande EV-laden',
  'Grid and home battery cover planned EV charging':
    'Het net en de thuisbatterij dekken het geplande EV-laden',
  'Grid setpoint steers home battery toward departure reserve':
    'Het netsetpoint stuurt de thuisbatterij naar de reserve bij vertrek'
} %}
{% if is_state('VALID', 'on') %}
GridPilot verwerkt geldige meetwaarden.
{% else %}
**Meetwaarden ongeldig.**
{% endif %}

- **Werkmodus:**
  {% if is_state('SHADOW', 'on') %}Schaduwmodus{% else %}Actieve aansturing{% endif %}
- **Aansturing:** {% if is_state('HEALTHY', 'on') %}gezond{% else %}storing{% endif %}
- **Berekend setpoint:** {{ calculated | round(0) }} W
- **Actief setpoint:** {{ actual | round(0) }} W
- **Verschil:** {{ difference | round(0) }} W
- **Modus:** {{ mode_labels.get(states('MODE'), states('MODE')) }}
- **Reden:** {{ reason_labels.get(states('REASON'), states('REASON')) }}
""".replace("CALCULATED", calculated).replace("ACTUAL", actual).replace(
        "VALID", valid
    ).replace("SHADOW", shadow).replace("HEALTHY", healthy).replace(
        "MODE", mode
    ).replace("REASON", reason)


def _ev_markdown(
    selected_mode: str,
    strategy: str,
    mode: str,
    reason: str,
    target: str,
    valid: str,
    healthy: str,
    current_limit: str | None,
) -> str:
    """Return the dynamic EV-control explanation."""
    current_line = (
        f"- **Actuele laadlimiet:** {{{{ states('{current_limit}') }}}} A\n"
        if current_limit
        else ""
    )
    return (
        """### Laadregeling
{% set selected = states('STRATEGY') %}
{% set selected_mode = states('SELECTED_MODE') %}
{% set strategy_labels = {
  'none': 'Uit',
  'pv': 'PV laden',
   'manual': 'Manueel',
   'battery_to_ev': 'Thuisbatterij naar EV',
   'departure': 'Vertrektijd'
} %}
{% set mode_labels = {
  'unavailable': 'Niet beschikbaar',
  'inactive': 'Inactief',
  'disconnected': 'Niet verbonden',
  'blocked': 'Geblokkeerd',
  'waiting': 'Wachten',
  'charging': 'Laden',
  'stop_delay': 'Stopvertraging',
  'restart_blocked': 'Herstart geblokkeerd'
} %}
{% set reason_labels = {
  'No GridPilot EV charging strategy is selected':
    'Er is geen GridPilot-laadstrategie geselecteerd',
  'EV is not connected': 'De EV is niet verbonden',
  'Battery grid charging blocks PV EV charging':
    'Laden via het net blokkeert PV-laden van de EV',
  'Available PV power supports EV charging':
    'Het beschikbare PV-vermogen volstaat om de EV te laden',
  'Available PV power is below the minimum charging current':
    'Het beschikbare PV-vermogen ligt onder de minimale laadstroom',
  'EV current follows the manual charging setting':
    'De EV-stroom volgt de handmatig ingestelde laadstroom',
  'Battery reserve SOC pauses battery-to-EV charging':
    'De batterijreserve onderbreekt laden van thuisbatterij naar EV',
  'Battery-to-EV charging started': 'Laden van thuisbatterij naar EV is gestart',
  'Grid import reduces battery-to-EV current':
    'Netafname verlaagt de laadstroom van thuisbatterij naar EV',
  'Battery reserve allows more EV current':
    'De batterijreserve laat een hogere EV-stroom toe',
  'Battery reserve requires less EV current':
    'De batterijreserve vereist een lagere EV-stroom',
  'Battery-to-EV current is within the target tolerance':
    'De laadstroom van thuisbatterij naar EV ligt binnen de doelmarge',
  'EV restart delay is active': 'De EV-herstartvertraging is actief',
  'PV charging started': 'PV-laden is gestart',
  'Waiting for sufficient PV power': 'Wachten op voldoende PV-vermogen',
  'PV stop delay elapsed': 'De PV-stopvertraging is verstreken',
  'Temporary PV shortage is buffered': 'Een tijdelijk PV-tekort wordt opgevangen',
   'EV current follows available PV power':
     'De EV-stroom volgt het beschikbare PV-vermogen',
   'EV target SOC has been reached': 'Het EV-doel-SOC is bereikt',
   'Maximum grid import leaves no EV charging capacity':
     'De maximale netafname laat geen EV-laadvermogen toe',
   'EV target SOC cannot be reached by departure time':
     'Het EV-doel-SOC is niet haalbaar tegen de vertrektijd',
   'EV current is planned for the departure time':
     'De EV-stroom is gepland voor de vertrektijd'
} %}
{% if selected_mode == 'Uit' %}
De laadregeling is uit.
{% else %}
GridPilot gebruikt **{{ strategy_labels.get(selected, selected_mode) }}**.
{% endif %}

- **Bedrijfsmodus:** {{ mode_labels.get(states('MODE'), states('MODE')) }}
- **Doelstroom:** {{ states('TARGET') }} A
CURRENT_LINE- **Meetwaarden:**
  {% if is_state('VALID', 'on') %}geldig{% else %}ongeldig{% endif %}
- **Aansturing:** {% if is_state('HEALTHY', 'on') %}gezond{% else %}storing{% endif %}
- **Reden:** {{ reason_labels.get(states('REASON'), states('REASON')) }}
""".replace("SELECTED_MODE", selected_mode)
        .replace("STRATEGY", strategy)
        .replace("MODE", mode)
        .replace("TARGET", target)
        .replace("CURRENT_LINE", current_line)
        .replace("VALID", valid)
        .replace("HEALTHY", healthy)
        .replace("REASON", reason)
    )


def _departure_plan_markdown(
    operating_mode: str,
    reason: str,
    target_current: str,
    departure_time: str,
    target_soc: str,
) -> str:
    """Return the departure-time charging plan and deadline warning."""
    return """### Laadplan
{% set reason = states('REASON') %}
{% set target_current = states('TARGET_CURRENT') | float(0) %}
{% set departure = states('DEPARTURE_TIME') %}
{% set target_soc = states('TARGET_SOC') | float(0) %}
{% if reason == 'EV target SOC cannot be reached by departure time' %}
**Deadline onhaalbaar.** GridPilot laadt met het maximaal beschikbare vermogen.
{% elif is_state('MODE', 'waiting') and reason == 'EV target SOC has been reached' %}
**Laaddoel bereikt.** De EV wacht tot de vertrektijd.
{% else %}
GridPilot plant het laden vanaf nu om het doel op tijd te halen.
{% endif %}

- **Vertrek:** {{ departure[:5] }}
- **Doel-SOC:** {{ target_soc | round(0) }}%
- **Geplande laadstroom:** {{ target_current | round(1) }} A
""".replace("MODE", operating_mode).replace("REASON", reason).replace(
        "TARGET_CURRENT", target_current
    ).replace("DEPARTURE_TIME", departure_time).replace("TARGET_SOC", target_soc)


def _soc_load_markdown(sensor: str) -> str:
    """Return the flexible-device status and SOC switching rules."""
    return """### Flexibele apparaten
{% set devices = state_attr('SENSOR', 'devices') or [] %}
{% set active = state_attr('SENSOR', 'active_control') %}
{% if not devices %}
Er zijn momenteel geen apparaten geconfigureerd voor GridPilot SOC-sturing.
{% else %}
{% if not active %}**Sturing is uitgeschakeld.**{% endif %}
{% for device in devices %}
{% set on_threshold = device.turn_on_at_soc %}
{% set off_threshold = device.turn_off_at_soc %}
{% set on_label = (
  'Nooit' if on_threshold in [none, 'never']
  else on_threshold | float | round(0) ~ '% SOC'
) %}
{% set off_label = (
  'Nooit' if off_threshold in [none, 'never']
  else off_threshold | float | round(0) ~ '% SOC'
) %}
- **{{ device.name }}** ({{ device.state }})
  - Aan bij {{ on_label }}
  - Uit bij {{ off_label }}
{% endfor %}
{% endif %}

GridPilot gebruikt SOC-drempels, geen vaste tijdstippen.
""".replace("SENSOR", sensor)
