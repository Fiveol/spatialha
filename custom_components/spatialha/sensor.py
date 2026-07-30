from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    dr = await async_get_device_registry(hass)
    entities: list[SensorEntity] = []

    for server_id in data.get("servers", {}):
        _LOGGER.debug("Creating scanner device for %s", server_id)
        _ensure_scanner_device(dr, config_entry.entry_id, server_id)
        entities.append(SpatialHAScannerSensor(hass, server_id))

    for addr, dev in data.get("devices", {}).items():
        _LOGGER.debug("Creating BLE device for %s", addr)
        _ensure_ble_device(dr, config_entry.entry_id, addr, dev)

    entities.append(SpatialHAMQTTStatusSensor(hass))

    if entities:
        async_add_entities(entities)

    data["add_scanner_sensor"] = callback(lambda sid: async_add_entities([SpatialHAScannerSensor(hass, sid)]))
    data["ensure_scanner_device"] = callback(lambda sid: _ensure_scanner_device(dr, config_entry.entry_id, sid))
    data["ensure_ble_device"] = callback(lambda addr, dev: _ensure_ble_device(dr, config_entry.entry_id, addr, dev))
    data["mqtt_connected"] = False

    _LOGGER.info("Sensor platform setup complete: %d scanners, %d BLE devices", len(data.get("servers", {})), len(data.get("devices", {})))


def _ensure_scanner_device(dr, config_entry_id: str, server_id: str) -> None:
    dr.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, f"scanner_{server_id}")},
        name=f"SpatialBLE Scanner {server_id}",
        manufacturer="SpatialHA",
        model="SpatialBLE Scanner",
        sw_version=VERSION,
    )


def _ensure_ble_device(dr, config_entry_id: str, address: str, dev: dict) -> None:
    dr.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, f"ble_{address}")},
        name=dev.get("name") or address,
        manufacturer="Unknown",
        model="BLE Device",
    )


class SpatialHAMQTTStatusSensor(SensorEntity):
    _attr_icon = "mdi:router-wireless"
    _attr_unique_id = f"{DOMAIN}_mqtt_status"
    _attr_name = "SpatialHA MQTT Status"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @property
    def native_value(self) -> str:
        data = self.hass.data.get(DOMAIN, {})
        mqtt_client = data.get("mqtt_client")
        if not mqtt_client:
            return "Not configured"
        if data.get("mqtt_connected"):
            host = mqtt_client.host
            return f"Connected to {host}"
        return "Disconnected"


class SpatialHAScannerSensor(SensorEntity):
    _attr_icon = "mdi:bluetooth"

    def __init__(self, hass: HomeAssistant, server_id: str) -> None:
        self.hass = hass
        self.server_id = server_id
        self._attr_unique_id = f"{DOMAIN}_scanner_{server_id}"
        self._attr_name = f"SpatialBLE Scanner {server_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"scanner_{server_id}")},
        }

    @property
    def native_value(self) -> int:
        data = self.hass.data.get(DOMAIN, {})
        devices = data.get("devices", {})
        return sum(1 for d in devices.values() if d.get("server_id") == self.server_id)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.hass.data.get(DOMAIN, {})
        servers = data.get("servers", {})
        info = servers.get(self.server_id, {})
        return {"ota_ip": info.get("ota_ip", ""), "ota_port": info.get("ota_port", 0), "last_seen": info.get("last_seen", 0)}
