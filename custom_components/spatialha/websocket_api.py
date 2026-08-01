from __future__ import annotations

import json

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MQTT_PORT,
    DOMAIN,
    VERSION,
)
from .floorplan import FloorPlanStore
from .mqtt import MQTTClient

MAX_PLAN_BYTES = 512 * 1024

_PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
_INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=1, max=3600))


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
            "mqtt_connected": data.get("mqtt_connected", False),
        },
    )


@websocket_api.websocket_command({"type": "spatialha/config"})
@websocket_api.async_response
async def handle_get_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_found", "No spatialha config entry")
        return
    config = dict(entries[0].data)
    config.pop(CONF_MQTT_PASSWORD, None)
    config["mqtt_connected"] = hass.data.get(DOMAIN, {}).get("mqtt_connected", False)
    connection.send_result(msg["id"], config)


@websocket_api.websocket_command(
    {
        "type": "spatialha/update_config",
        vol.Optional(CONF_MQTT_HOST): str,
        vol.Optional(CONF_MQTT_PORT): _PORT,
        vol.Optional(CONF_MQTT_USERNAME): str,
        vol.Optional(CONF_MQTT_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL): _INTERVAL,
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
    for key in (
        CONF_MQTT_HOST,
        CONF_MQTT_PORT,
        CONF_MQTT_USERNAME,
        CONF_MQTT_PASSWORD,
        CONF_UPDATE_INTERVAL,
    ):
        if key not in msg:
            continue
        # Never overwrite a stored password with an empty value.
        if key == CONF_MQTT_PASSWORD and not msg[key]:
            continue
        new_data[key] = msg[key]
    hass.config_entries.async_update_entry(entry, data=new_data)

    mqtt_keys = (
        CONF_MQTT_HOST,
        CONF_MQTT_PORT,
        CONF_MQTT_USERNAME,
        CONF_MQTT_PASSWORD,
    )
    if any(k in msg for k in mqtt_keys):
        await _restart_mqtt(hass)

    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({"type": "spatialha/floorplan/get"})
@websocket_api.async_response
async def handle_floorplan_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    store: FloorPlanStore | None = hass.data.get(DOMAIN, {}).get("floorplan_store")
    if store is None:
        connection.send_error(msg["id"], "not_found", "Floor plan store not available")
        return
    plan = await store.load()
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command({"type": "spatialha/floorplan/save", "plan": dict})
@websocket_api.async_response
async def handle_floorplan_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    store: FloorPlanStore | None = hass.data.get(DOMAIN, {}).get("floorplan_store")
    if store is None:
        connection.send_error(msg["id"], "not_found", "Floor plan store not available")
        return
    if len(json.dumps(msg["plan"])) > MAX_PLAN_BYTES:
        connection.send_error(
            msg["id"], "plan_too_large", "Floor plan payload is too large"
        )
        return
    await store.save(msg["plan"])
    connection.send_result(msg["id"], {"success": True})


async def _restart_mqtt(hass: HomeAssistant) -> None:
    data = hass.data.get(DOMAIN, {})
    if not data:
        return
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return
    client = data.get("mqtt_client")
    if client:
        await client.async_stop()
    cfg = entries[0].data
    data["mqtt_client"] = MQTTClient(
        hass,
        host=cfg.get(CONF_MQTT_HOST, ""),
        port=cfg.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT),
        username=cfg.get(CONF_MQTT_USERNAME, ""),
        password=cfg.get(CONF_MQTT_PASSWORD, ""),
    )
    await data["mqtt_client"].async_start()


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, handle_version)
    websocket_api.async_register_command(hass, handle_ble_devices)
    websocket_api.async_register_command(hass, handle_get_config)
    websocket_api.async_register_command(hass, handle_update_config)
    websocket_api.async_register_command(hass, handle_floorplan_get)
    websocket_api.async_register_command(hass, handle_floorplan_save)
