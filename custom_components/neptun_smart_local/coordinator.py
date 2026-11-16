"""Координатор опроса контроллера Neptun Smart."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL
from .device import NeptunSmart

_LOGGER = logging.getLogger(__name__)


class NeptunSmartCoordinator(DataUpdateCoordinator[bool]):
    """Единый координатор опроса для всех платформ интеграции."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: NeptunSmart,
        scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self.device = device
        self.entry = entry
        kwargs = {
            "name": f"{device.get_name()}_coordinator",
            "update_interval": timedelta(seconds=scan_interval_seconds),
        }
        try:
            super().__init__(hass, _LOGGER, config_entry=entry, **kwargs)
        except TypeError:
            super().__init__(hass, _LOGGER, **kwargs)

    async def _async_update_data(self) -> bool:
        """Выполняет цикл пакетного опроса всех регистров устройства."""
        try:
            success = await self.device.update()
        except Exception as err:
            raise UpdateFailed(
                f"Ошибка связи с контроллером {self.device.get_name()}: {err}"
            ) from err

        if not success:
            raise UpdateFailed(
                f"Контроллер {self.device.get_name()} ({self.device.host}:{self.device.port}) не отвечает"
            )
        return True

