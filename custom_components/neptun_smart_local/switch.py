"""Переключатели кранов и режимов работы контроллера Neptun Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NeptunSmartCoordinator
from .entity import NeptunEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Регистрация переключателей Neptun Smart."""
    coordinator: NeptunSmartCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    switches: list[SwitchEntity] = [Valve1Zone(coordinator)]
    if device.get_dual_group_mode():
        switches.append(Valve2Zone(coordinator))

    switches.extend(
        [
            FloorWashingMode(coordinator),
            ConnectingWirelessSensorsMode(coordinator),
            DualGroupMode(coordinator),
            CloseValveWhenLostSensorsMode(coordinator),
            LockButtons(coordinator),
        ]
    )
    async_add_entities(switches)


class Valve1Zone(NeptunEntity, SwitchEntity):
    """Кран 1 зоны (или оба крана в однозонном режиме)."""

    _attr_translation_key = "valve_zone_1"
    _attr_icon = "mdi:pipe-valve"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_Valve_1_zone"

    @property
    def is_on(self) -> bool:
        return self._device.get_first_group_valve_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_first_group_valve_state(False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_first_group_valve_state(True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class Valve2Zone(NeptunEntity, SwitchEntity):
    """Кран 2 зоны (в двухзонном режиме)."""

    _attr_translation_key = "valve_zone_2"
    _attr_icon = "mdi:pipe-valve"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_Valve_2_zone"

    @property
    def is_on(self) -> bool:
        return self._device.get_second_group_valve_state()

    @property
    def available(self) -> bool:
        return super().available and self._device.get_dual_group_mode()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_second_group_valve_state(False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_second_group_valve_state(True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class FloorWashingMode(NeptunEntity, SwitchEntity):
    """Режим мойки пола (временное игнорирование датчиков протечки)."""

    _attr_translation_key = "floor_washing_mode"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_Floor_washing_mode"

    @property
    def is_on(self) -> bool:
        return self._device.get_floor_washing_mode()

    @property
    def icon(self) -> str:
        return (
            "mdi:pail"
            if self._device.get_floor_washing_mode()
            else "mdi:pail-off"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_floor_washing_mode(False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_floor_washing_mode(True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class ConnectingWirelessSensorsMode(NeptunEntity, SwitchEntity):
    """Режим сопряжения беспроводных датчиков."""

    _attr_translation_key = "pairing_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_Connecting_wireless_sensors_mode"
        )

    @property
    def is_on(self) -> bool:
        return self._device.get_connecting_wireless_sensors_mode()

    @property
    def icon(self) -> str:
        return (
            "mdi:router-wireless"
            if self._device.get_connecting_wireless_sensors_mode()
            else "mdi:router-wireless-off"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_connecting_wireless_sensors_mode(False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_connecting_wireless_sensors_mode(True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class DualGroupMode(NeptunEntity, SwitchEntity):
    """Двухзонный режим работы кранов и датчиков."""

    _attr_translation_key = "dual_group_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_dual_group_mode"

    @property
    def is_on(self) -> bool:
        return self._device.get_dual_group_mode()

    @property
    def icon(self) -> str:
        return (
            "mdi:numeric-2-circle-outline"
            if self._device.get_dual_group_mode()
            else "mdi:numeric-1-circle-outline"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_dual_group_mode(False)
        self.async_write_ha_state()
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.coordinator.entry.entry_id)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_dual_group_mode(True)
        self.async_write_ha_state()
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.coordinator.entry.entry_id)
        )


class CloseValveWhenLostSensorsMode(NeptunEntity, SwitchEntity):
    """Автоматически закрывать краны при потере связи с радиодатчиками."""

    _attr_translation_key = "close_valve_on_sensor_loss"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:pipe-valve"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_Close_valve_when_lost_sensors_mode"
        )

    @property
    def is_on(self) -> bool:
        return self._device.get_close_valve_when_lost_sensors_mode()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_close_valve_when_lost_sensors_mode(False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_close_valve_when_lost_sensors_mode(True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LockButtons(NeptunEntity, SwitchEntity):
    """Блокировка физических кнопок на модуле."""

    _attr_translation_key = "lock_buttons"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_Lock_buttons"

    @property
    def is_on(self) -> bool:
        return self._device.get_lock_buttons()

    @property
    def icon(self) -> str:
        return (
            "mdi:keyboard-off-outline"
            if self._device.get_lock_buttons()
            else "mdi:keyboard-close-outline"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_lock_buttons(False)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_lock_buttons(True)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

