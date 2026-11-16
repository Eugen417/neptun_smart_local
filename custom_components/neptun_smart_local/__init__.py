"""Инициализация интеграции Neptun Smart Local."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_HOST_IP,
    CONF_HOST_PORT,
    CONF_KNOWN_COUNTERS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import NeptunSmartCoordinator
from .device import NeptunSmart

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка записи интеграции Neptun Smart Local."""
    hass.data.setdefault(DOMAIN, {})

    name: str = entry.data.get(CONF_NAME, entry.title or DEFAULT_NAME)
    host_ip: str = entry.options.get(CONF_HOST_IP, entry.data[CONF_HOST_IP])
    host_port = int(
        entry.options.get(CONF_HOST_PORT, entry.data.get(CONF_HOST_PORT, DEFAULT_PORT))
    )
    scan_interval = int(
        entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    )
    known_counters: list[int] = list(
        entry.options.get(
            CONF_KNOWN_COUNTERS, entry.data.get(CONF_KNOWN_COUNTERS, [])
        )
    )

    device = NeptunSmart(
        hass=hass,
        name=name,
        host_ip=host_ip,
        host_port=host_port,
        known_counters=known_counters,
    )

    try:
        await device.init_sensors()
    except (ConnectionError, TimeoutError, OSError, ValueError) as err:
        await device.async_close()
        raise ConfigEntryNotReady(
            f"Контроллер {name} ({host_ip}:{host_port}) пока не готов: {err}"
        ) from err

    # Обновляем кэш активных счётчиков, чтобы при рестарте сущности не терялись
    current_counters = device.get_counter_addresses()
    if current_counters and current_counters != known_counters:
        new_options = {**entry.options, CONF_KNOWN_COUNTERS: current_counters}
        hass.config_entries.async_update_entry(entry, options=new_options)

    coordinator = NeptunSmartCoordinator(
        hass=hass,
        entry=entry,
        device=device,
        scan_interval_seconds=scan_interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await device.async_close()
        raise

    async def _async_close_on_stop(_event: Event) -> None:
        """Гарантированно освобождает TCP-сокет контроллера при остановке HA."""
        await device.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_on_stop)
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции и закрытие Modbus TCP соединения."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: NeptunSmartCoordinator | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator is not None:
            await coordinator.device.async_close()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезагрузка записи при изменении параметров в OptionsFlow."""
    await hass.config_entries.async_reload(entry.entry_id)

