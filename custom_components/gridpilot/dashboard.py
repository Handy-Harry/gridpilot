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
    CONF_EV_BATTERY_MIN_SOC,
    CONF_EV_BATTERY_MODE,
    CONF_EV_CURRENT_LIMIT,
    CONF_EV_MANUAL_CURRENT,
    CONF_EV_MANUAL_MODE,
    CONF_EV_MODE,
    CONF_EV_PHASE_MODE,
    CONF_EV_POWER,
    CONF_EV_PV_MODE,
    CONF_EV_VEHICLE_SOC,
    CONF_GRID_SETPOINT,
    DEFAULT_BATTERY_CHARGE_POSITIVE,
    DEFAULT_EV_BATTERY_MODE,
    DEFAULT_EV_MANUAL_MODE,
    DEFAULT_EV_PV_MODE,
    DOMAIN,
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
            "setpoint_entity": calculated_setpoint,
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
    if not options.get(CONF_EV_MODE):
        return []

    strategy = _gridpilot_entity(hass, entry, "sensor", "ev_strategy")
    operating_mode = _gridpilot_entity(hass, entry, "sensor", "ev_operating_mode")
    reason = _gridpilot_entity(hass, entry, "sensor", "ev_control_reason")
    target_current = _gridpilot_entity(hass, entry, "sensor", "ev_target_current")
    priority = _gridpilot_entity(hass, entry, "number", "ev_priority")
    measurements_valid = _gridpilot_entity(
        hass, entry, "binary_sensor", "ev_measurements_valid"
    )
    actuation_healthy = _gridpilot_entity(
        hass, entry, "binary_sensor", "ev_actuation_healthy"
    )

    cards: list[dict[str, Any]] = [
        {
            "type": "heading",
            "heading": "Wagen laden",
            "heading_style": "title",
            "icon": "mdi:ev-station",
        },
        {
            "type": "tile",
            "entity": options[CONF_EV_MODE],
            "name": "Laadmodus kiezen",
            "icon": "mdi:ev-station",
            "features": [{"type": "select-options"}],
        },
        {
            "type": "conditional",
            "conditions": [
                {
                    "condition": "state",
                    "entity": options[CONF_EV_MODE],
                    "state": options.get(CONF_EV_PV_MODE, DEFAULT_EV_PV_MODE),
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
            "features": [feature],
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
                {"type": "select-options"},
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
                        "entity": options[CONF_EV_MODE],
                        "state": options.get(
                            CONF_EV_MANUAL_MODE, DEFAULT_EV_MANUAL_MODE
                        ),
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
                        "entity": options[CONF_EV_MODE],
                        "state": options.get(
                            CONF_EV_BATTERY_MODE, DEFAULT_EV_BATTERY_MODE
                        ),
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
{% if is_state('VALID', 'on') %}
GridPilot verwerkt geldige meetwaarden.
{% else %}
**Meetwaarden ongeldig.**
{% endif %}

- **Werkmodus:**
  {% if is_state('SHADOW', 'on') %}Shadow mode{% else %}Actieve aansturing{% endif %}
- **Aansturing:** {% if is_state('HEALTHY', 'on') %}gezond{% else %}storing{% endif %}
- **Berekend setpoint:** {{ calculated | round(0) }} W
- **Actief setpoint:** {{ actual | round(0) }} W
- **Verschil:** {{ difference | round(0) }} W
- **Modus:** {{ states('MODE') }}
- **Reden:** {{ states('REASON') }}
""".replace("CALCULATED", calculated).replace("ACTUAL", actual).replace(
        "VALID", valid
    ).replace("SHADOW", shadow).replace("HEALTHY", healthy).replace(
        "MODE", mode
    ).replace("REASON", reason)


def _ev_markdown(
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
{% if selected == 'none' %}
De laadregeling is uit.
{% else %}
GridPilot gebruikt strategie **{{ selected }}**.
{% endif %}

- **Bedrijfsmodus:** {{ states('MODE') }}
- **Doelstroom:** {{ states('TARGET') }} A
CURRENT_LINE- **Meetwaarden:**
  {% if is_state('VALID', 'on') %}geldig{% else %}ongeldig{% endif %}
- **Aansturing:** {% if is_state('HEALTHY', 'on') %}gezond{% else %}storing{% endif %}
- **Reden:** {{ states('REASON') }}
""".replace("STRATEGY", strategy)
        .replace("MODE", mode)
        .replace("TARGET", target)
        .replace("CURRENT_LINE", current_line)
        .replace("VALID", valid)
        .replace("HEALTHY", healthy)
        .replace("REASON", reason)
    )
