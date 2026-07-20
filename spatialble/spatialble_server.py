"""
spatialble_server - BLE advertisement scanner that publishes to MQTT.
"""

import asyncio
import json
import socket
import time
import logging

from bleak import BleakScanner
import paho.mqtt.client as mqtt

_has_callback_api = hasattr(mqtt, 'CallbackAPIVersion')
if _has_callback_api:
    from paho.mqtt.client import CallbackAPIVersion

from spatialble_config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    HEARTBEAT_INTERVAL,
    OTA_PORT,
)

MQTT_TOPIC = "spatialble"
MQTT_RC_MESSAGES = {
    0: "Connection accepted",
    1: "Connection refused: unacceptable protocol version",
    2: "Connection refused: identifier rejected",
    3: "Connection refused: server unavailable",
    4: "Connection refused: bad user name or password",
    5: "Connection refused: not authorized",
}

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


class SpatialBLEServer:
    def __init__(self):
        self.server_id = socket.gethostname()
        kwargs = dict(client_id=self.server_id)
        if _has_callback_api:
            kwargs['callback_api_version'] = CallbackAPIVersion.VERSION1
        self.mqtt_client = mqtt.Client(**kwargs)
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self._last_publish = {}
        self._running = True

    def _on_connect(self, client, userdata, flags, rc):
        msg = MQTT_RC_MESSAGES.get(rc, f"Unknown code {rc}")
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker")
        else:
            _LOGGER.error("MQTT connection failed: %s", msg)

    def _on_disconnect(self, client, userdata, rc):
        msg = MQTT_RC_MESSAGES.get(rc, f"Unknown code {rc}")
        _LOGGER.warning("MQTT disconnected: %s", msg)
        if rc != 0 and self._running:
            _LOGGER.info("Reconnecting in 10 seconds...")
            client.reconnect_delay_set(delay=10)
            client.reconnect()

    def _publish(self, payload: dict):
        topic = f"{MQTT_TOPIC}/{self.server_id}"
        self.mqtt_client.publish(topic, json.dumps(payload), qos=1)

    @staticmethod
    def _get_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "0.0.0.0"

    async def _heartbeat_loop(self):
        ota_ip = self._get_ip()
        while self._running:
            payload = {
                "type": "heartbeat",
                "server_id": self.server_id,
                "timestamp": time.time(),
                "ota_ip": ota_ip,
                "ota_port": OTA_PORT,
            }
            self._publish(payload)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _scan_callback(self, device, advertisement_data):
        address = device.address
        rssi = advertisement_data.rssi
        name = advertisement_data.local_name or ""
        tx_power = advertisement_data.tx_power
        service_uuids = list(advertisement_data.service_uuids or [])

        manufacturer_data = {}
        if advertisement_data.manufacturer_data:
            for mfr_id, data in advertisement_data.manufacturer_data.items():
                manufacturer_data[str(mfr_id)] = data.hex()

        service_data = {}
        if advertisement_data.service_data:
            for uuid, data in advertisement_data.service_data.items():
                service_data[str(uuid)] = data.hex()

        now = time.time()
        last = self._last_publish.get(address)
        if last:
            last_time, last_rssi = last
            if abs(rssi - last_rssi) < 5 and (now - last_time) < 30:
                return

        self._last_publish[address] = (now, rssi)

        payload = {
            "type": "advertisement",
            "server_id": self.server_id,
            "timestamp": now,
            "device": {
                "address": address,
                "rssi": rssi,
                "name": name,
                "tx_power": tx_power,
                "manufacturer_data": manufacturer_data,
                "service_uuids": service_uuids,
                "service_data": service_data,
            },
        }
        self._publish(payload)

    async def _connect_with_retry(self):
        while self._running:
            try:
                self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
                self.mqtt_client.loop_start()
                _LOGGER.info("MQTT client started")
                return
            except Exception as e:
                _LOGGER.error("MQTT connection failed: %s (retrying in 10s)", e)
                await asyncio.sleep(10)

    async def run(self):
        await self._connect_with_retry()
        if not self._running:
            return

        _LOGGER.info("Starting BLE scan (server_id=%s)", self.server_id)

        asyncio.create_task(self._heartbeat_loop())

        scanner = BleakScanner(
            detection_callback=self._scan_callback,
        )
        await scanner.start()

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await scanner.stop()
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def main():
    server = SpatialBLEServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down...")
        server._running = False


if __name__ == "__main__":
    main()
