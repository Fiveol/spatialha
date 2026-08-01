from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.floorplan"


class FloorPlanStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = storage.Store[dict](hass, STORAGE_VERSION, STORAGE_KEY)

    async def load(self) -> dict:
        data = await self._store.async_load()
        if data is None:
            data = {"unit": "m", "floors": []}
        return data

    async def save(self, data: dict) -> None:
        await self._store.async_save(data)
