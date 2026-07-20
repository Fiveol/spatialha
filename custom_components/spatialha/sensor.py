from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, VERSION


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SpatialHAStatusSensor()])


class SpatialHAStatusSensor(SensorEntity):
    _attr_name = "SpatialHA Status"
    _attr_unique_id = "spatialha_status"
    _attr_native_value = "running"
    _attr_extra_state_attributes = {"version": VERSION}
