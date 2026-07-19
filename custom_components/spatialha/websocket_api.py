from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import VERSION


@websocket_api.websocket_command({"type": "spatialha/version"})
@websocket_api.async_response
async def handle_version(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    connection.send_result(msg["id"], {"version": VERSION})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, handle_version)
