"""Базовый класс сущностей Neptun Smart Local."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NeptunSmartCoordinator
from .device import NeptunSmart


class NeptunEntity(CoordinatorEntity[NeptunSmartCoordinator]):
    """Общий базовый класс для всех сущностей контроллера Neptun Smart."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._device: NeptunSmart = coordinator.device

    @property
    def device_info(self) -> DeviceInfo:
        """Единое описание устройства в реестре Home Assistant."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.get_name())},
            name=self._device.get_name(),
            manufacturer="Teploluxe (Neptun)",
            model=f"Neptun Smart ({self._device.host}:{self._device.port})",
        )

    @property
    def available(self) -> bool:
        """Доступность сущности зависит от успеха опроса координатора и флага связи."""
        return super().available and self._device.is_connected()
