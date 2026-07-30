from __future__ import annotations

import json
import logging
import time

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant

from .const import DOMAIN, MQTT_TOPIC

_LOGGER = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self, hass: HomeAssistant, host: str, port: int, username: str, password: str) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client: mqtt.Client | None = None
        self._running = False

    async def async_start(self) -> None:
        if not self.host:
            _LOGGER.warning("MQTT not configured - no host set")
            return
        self._running = True

        def on_connect(client, userdata, flags, rc) -> None:
            if rc == 0:
                _LOGGER.info("Connected to MQTT broker at %s:%s", self.host, self.port)
                self.hass.data[DOMAIN]["mqtt_connected"] = True
                client.subscribe(MQTT_TOPIC)
                _LOGGER.info("Subscribed to %s", MQTT_TOPIC)
            else:
                _LOGGER.error("MQTT connection failed with rc=%s", rc)

        def on_disconnect(client, userdata, rc) -> None:
            self.hass.data[DOMAIN]["mqtt_connected"] = False
            if rc != 0:
                _LOGGER.warning("MQTT disconnected (rc=%s), will auto-reconnect", rc)

        def on_message(client, userdata, msg) -> None:
            self.hass.loop.call_soon_threadsafe(self._handle_message, msg.topic, msg.payload)

        self.client = mqtt.Client(client_id=f"spatialha-{id(self)}")
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.on_message = on_message

        try:
            _LOGGER.info("Connecting to MQTT broker at %s:%s ...", self.host, self.port)
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            _LOGGER.error("Failed to connect to MQTT broker: %s", e)

    async def async_stop(self) -> None:
        self._running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None

    def _handle_message(self, topic: str, payload: bytes) -> None:
        data = self.hass.data.setdefault(DOMAIN, {})
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON on %s: %s", topic, payload[:200])
            return

        msg_type = parsed.get("type")
        _LOGGER.debug("MQTT msg on %s: type=%s", topic, msg_type)

        if msg_type == "heartbeat":
            server_id = parsed.get("server_id")
            if not server_id:
                return
            servers = data.setdefault("servers", {})
            is_new = server_id not in servers
            servers[server_id] = {
                "server_id": server_id,
                "ota_ip": parsed.get("ota_ip", ""),
                "ota_port": parsed.get("ota_port", 0),
                "last_seen": parsed.get("timestamp", time.time()),
            }
            if is_new:
                _LOGGER.info("New scanner discovered: %s", server_id)
                ensure = data.get("ensure_scanner_device")
                if ensure:
                    ensure(server_id)
                add_sensor = data.get("add_scanner_sensor")
                if add_sensor:
                    add_sensor(server_id)

        elif msg_type == "advertisement":
            device = parsed.get("device", {})
            addr = device.get("address")
            if not addr:
                return
            devices = data.setdefault("devices", {})
            is_new = addr not in devices
            devices[addr] = {
                "address": addr,
                "name": device.get("name", ""),
                "rssi": device.get("rssi"),
                "tx_power": device.get("tx_power"),
                "manufacturer_data": device.get("manufacturer_data", {}),
                "service_uuids": device.get("service_uuids", []),
                "service_data": device.get("service_data", {}),
                "server_id": parsed.get("server_id"),
                "last_seen": parsed.get("timestamp", time.time()),
            }
            if is_new:
                _LOGGER.info("New BLE device discovered: %s (%s) via %s", device.get("name", ""), addr, parsed.get("server_id"))
                ensure = data.get("ensure_ble_device")
                if ensure:
                    ensure(addr, devices[addr])
