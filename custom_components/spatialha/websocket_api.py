from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION


@websocket_api.websocket_command({"type": "spatialha/version"})
@websocket_api.async_response
async def handle_version(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    connection.send_result(msg["id"], {"version": VERSION})


@websocket_api.websocket_command({"type": "spatialha/ble/devices"})
@websocket_api.async_response
async def handle_ble_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    data = hass.data.get(DOMAIN, {})
    connection.send_result(
        msg["id"],
        {
            "devices": list(data.get("devices", {}).values()),
            "servers": list(data.get("servers", {}).values()),
        },
    )


@websocket_api.websocket_command({"type": "spatialha/config"})
@websocket_api.async_response
async def handle_get_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    config = dict(entry.data)
    config.pop("mqtt_password", None)
    connection.send_result(msg["id"], config)


@websocket_api.websocket_command(
    {
        "type": "spatialha/update_config",
        vol.Optional("mqtt_host"): str,
        vol.Optional("mqtt_port"): int,
        vol.Optional("mqtt_username"): str,
        vol.Optional("mqtt_password"): str,
    }
)
@websocket_api.async_response
async def handle_update_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_found", "No spatialha config entry")
        return
    entry = entries[0]
    new_data = dict(entry.data)
    for key in ("mqtt_host", "mqtt_port", "mqtt_username", "mqtt_password"):
        if key in msg:
            new_data[key] = msg[key]
    hass.config_entries.async_update_entry(entry, data=new_data)
    connection.send_result(msg["id"], {"success": True})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, handle_version)
    websocket_api.async_register_command(hass, handle_ble_devices)
    websocket_api.async_register_command(hass, handle_get_config)
    websocket_api.async_register_command(hass, handle_update_config)
