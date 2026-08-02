from __future__ import annotations

import json
import logging
import time

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant

from .const import DOMAIN, MQTT_TOPIC

_LOGGER = logging.getLogger(__name__)

# Bound the in-memory device cache; entries not seen in this window are pruned
# when the cache grows too large.
MAX_DEVICES = 500
DEVICE_TTL_SECONDS = 24 * 60 * 60
CONNECT_TIMEOUT = 10


class MQTTClient:
    """MQTT bridge to SpatialBLE scanners, resilient to broker outages."""

    def __init__(
        self, hass: HomeAssistant, host: str, port: int, username: str, password: str
    ) -> None:
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
        if self._running:
            _LOGGER.debug("MQTT client already running")
            return
        self._running = True
        data = self.hass.data.setdefault(DOMAIN, {})
        data["mqtt_connected"] = False

        def on_connect(client, userdata, flags, reason_code, properties) -> None:
            data = self.hass.data.get(DOMAIN, {})
            if not data:
                return
            if reason_code.is_failure:
                _LOGGER.error("MQTT connection failed: %s", reason_code)
                data["mqtt_connected"] = False
            else:
                _LOGGER.info(
                    "Connected to MQTT broker at %s:%s", self.host, self.port
                )
                data["mqtt_connected"] = True
                client.subscribe(MQTT_TOPIC)
                _LOGGER.info("Subscribed to %s", MQTT_TOPIC)

        def on_disconnect(client, userdata, disconnect_flags, reason_code, properties) -> None:
            data = self.hass.data.get(DOMAIN, {})
            if data:
                data["mqtt_connected"] = False
            if not reason_code.is_failure:
                return
            _LOGGER.warning(
                "MQTT disconnected (%s), will auto-reconnect", reason_code
            )

        def on_subscribe(client, userdata, mid, reason_codes, properties) -> None:
            _LOGGER.debug("MQTT subscription confirmed: %s", reason_codes)

        def on_message(client, userdata, msg) -> None:
            try:
                self.hass.loop.call_soon_threadsafe(
                    self._handle_message, msg.topic, msg.payload
                )
            except RuntimeError:
                _LOGGER.debug("Event loop closed, dropping MQTT message on %s", msg.topic)

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"spatialha-{id(self)}",
        )
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.on_subscribe = on_subscribe
        self.client.on_message = on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_timeout = CONNECT_TIMEOUT

        try:
            # Non-blocking: the network loop thread (loop_start) performs the
            # connect and reconnects automatically with reconnect_delay_set.
            self.client.connect_async(self.host, self.port, keepalive=60)
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to initiate MQTT connection: %s", e)
            self._running = False
            return
        self.client.loop_start()
        _LOGGER.info(
            "MQTT client started (broker %s:%s), reconnect is automatic",
            self.host,
            self.port,
        )

    async def async_stop(self) -> None:
        self._running = False
        if not self.client:
            return
        client = self.client
        self.client = None
        try:
            # disconnect()/loop_stop() may block briefly (e.g. mid-reconnect),
            # so keep them off the event loop.
            await self.hass.async_add_executor_job(client.disconnect)
            await self.hass.async_add_executor_job(client.loop_stop)
        except Exception as e:  # noqa: BLE001
            _LOGGER.debug("Error while stopping MQTT client: %s", e)
        data = self.hass.data.get(DOMAIN, {})
        if data:
            data["mqtt_connected"] = False

    def _handle_message(self, topic: str, payload: bytes) -> None:
        data = self.hass.data.get(DOMAIN, {})
        if not data:
            return
        for forward in list(data.get("mqtt_monitor_subs", {}).values()):
            try:
                forward(topic, payload)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error forwarding MQTT message to monitor", exc_info=True)
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
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
            if not isinstance(device, dict):
                return
            addr = device.get("address")
            if not addr:
                return
            devices = data.setdefault("devices", {})
            server_id = parsed.get("server_id")
            is_new = addr not in devices
            existing = devices.get(addr, {})
            seen_by = dict(existing.get("seen_by", {}))
            if server_id:
                seen_by[server_id] = device.get("rssi")
            devices[addr] = {
                "address": addr,
                "name": device.get("name", ""),
                "rssi": device.get("rssi"),
                "tx_power": device.get("tx_power"),
                "manufacturer_data": device.get("manufacturer_data", {}),
                "service_uuids": device.get("service_uuids", []),
                "service_data": device.get("service_data", {}),
                "server_id": server_id,
                "seen_by": seen_by,
                "last_seen": parsed.get("timestamp", time.time()),
            }
            self._prune_devices(devices)
            if is_new:
                _LOGGER.info(
                    "New BLE device discovered: %s (%s) via %s",
                    device.get("name", ""),
                    addr,
                    server_id,
                )
                ensure = data.get("ensure_ble_device")
                if ensure:
                    ensure(addr, devices[addr])

    def _prune_devices(self, devices: dict) -> None:
        if len(devices) <= MAX_DEVICES:
            return
        cutoff = time.time() - DEVICE_TTL_SECONDS
        stale = [addr for addr, dev in devices.items() if dev.get("last_seen", 0) < cutoff]
        for addr in stale:
            del devices[addr]
        if stale:
            _LOGGER.info("Pruned %d stale BLE devices from cache", len(stale))
