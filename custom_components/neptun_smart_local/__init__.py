from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .device import NeptunSmart

PLATFORMS = [
    "binary_sensor",
    "select",
    "sensor",
    "switch",
]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    hass.data.setdefault(DOMAIN, {})

    name = entry.data["name"]
    host_port = entry.data["host_port"]
    host_ip = entry.data["host_ip"]
    device = NeptunSmart(hass, name, host_ip, host_port)
    
    try:
        await device.init_sensors()
    except ValueError as ex:
        raise ConfigEntryNotReady(f"Timeout while connecting {host_ip}") from ex

    # Инициализация фонового опросчика (DataUpdateCoordinator)
    async def async_update_data():
        try:
            await device.update()
        except Exception as err:
            raise UpdateFailed(f"Ошибка связи с устройством: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{name}_update_coordinator",
        update_method=async_update_data,
        update_interval=timedelta(seconds=5),
    )

    # Делаем первый опрос до загрузки платформ
    await coordinator.async_config_entry_first_refresh()
    
    # Привязываем координатор к объекту устройства, чтобы он не удалился сборщиком мусора
    device.coordinator = coordinator

    hass.data[DOMAIN][entry.entry_id] = device
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device = hass.data[DOMAIN].pop(entry.entry_id)
        # Обязательно закрываем соединение с Modbus при отключении интеграции
        await device._hub.disconnect()

    return unload_ok
