from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    DEFAULT_MQTT_PORT,
    DOMAIN,
)
from .mqtt import MQTTClient
from .websocket_api import async_register_websocket_commands


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    path = Path(__file__).parent / "frontend"

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/api/spatialha/static",
                str(path),
                cache_headers=False,
            )
        ]
    )

    async_remove_panel(hass, "spatialha")

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="spatialha",
        webcomponent_name="spatialha-panel",
        sidebar_icon="mdi:map",
        sidebar_title="SpatialHA",
        module_url="/api/spatialha/static/spatialha-panel.js",
        require_admin=False,
        config={},
    )

    async_register_websocket_commands(hass)

    mqtt_client = MQTTClient(
        hass,
        host=entry.data.get(CONF_MQTT_HOST, ""),
        port=entry.data.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT),
        username=entry.data.get(CONF_MQTT_USERNAME, ""),
        password=entry.data.get(CONF_MQTT_PASSWORD, ""),
    )
    hass.data[DOMAIN]["mqtt_client"] = mqtt_client
    await mqtt_client.async_start()

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    mqtt_client = hass.data.get(DOMAIN, {}).get("mqtt_client")
    if mqtt_client:
        await mqtt_client.async_stop()
    async_remove_panel(hass, "spatialha")
    return True
