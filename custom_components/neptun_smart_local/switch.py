from __future__ import annotations

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NeptunSmart
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(HomeAssistant, config_entry, async_add_entities):
    device: NeptunSmart = HomeAssistant.data[DOMAIN][config_entry.entry_id]
    switches = []
    
    switches.append(Valve1Zone(device))
    
    if device.get_dual_group_mode():
        switches.append(Valve2Zone(device))
        
    switches.append(FloorWashingMode(device))
    switches.append(ConnectingWirelessSensorsMode(device))
    switches.append(DualGroupMode(device))
    switches.append(CloseValveWhenLostSensorsMode(device))
    switches.append(LockButtons(device))
    
    async_add_entities(switches, update_before_add=False)


class Valve1Zone(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Вентиль 1 зоны"
        self._attr_unique_id = f"{device.get_name()}_Valve_1_zone"

    @property
    def is_on(self):
        return self._device.get_first_group_valve_state()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_first_group_valve_state(False)
        if not self._device.get_dual_group_mode():
            await self._device.set_second_group_valve_state(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_first_group_valve_state(True)
        if not self._device.get_dual_group_mode():
            await self._device.set_second_group_valve_state(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:pipe-valve"


class Valve2Zone(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Вентиль 2 зоны"
        self._attr_unique_id = f"{device.get_name()}_Valve_2_zone"

    @property
    def is_on(self):
        return self._device.get_second_group_valve_state()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_second_group_valve_state(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_second_group_valve_state(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:pipe-valve"


class FloorWashingMode(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Режим мойки пола"
        self._attr_unique_id = f"{device.get_name()}_Floor_washing_mode"

    @property
    def is_on(self):
        return self._device.get_floor_washing_mode()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_floor_washing_mode(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_floor_washing_mode(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:pail" if self._device.get_floor_washing_mode() else "mdi:pail-off"


class ConnectingWirelessSensorsMode(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Режим сопряжения радиодатчиков"
        self._attr_unique_id = f"{device.get_name()}_Connecting_wireless_sensors_mode"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return self._device.get_connecting_wireless_sensors_mode()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_connecting_wireless_sensors_mode(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_connecting_wireless_sensors_mode(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:router-wireless" if self._device.get_connecting_wireless_sensors_mode() else "mdi:router-wireless-off"


class DualGroupMode(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Двухзонный режим"
        self._attr_unique_id = f"{device.get_name()}_dual_group_mode"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return self._device.get_dual_group_mode()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_dual_group_mode(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_dual_group_mode(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:numeric-2-circle-outline" if self._device.get_dual_group_mode() else "mdi:numeric-1-circle-outline"


class CloseValveWhenLostSensorsMode(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Закрывать краны при потере связи"
        self._attr_unique_id = f"{device.get_name()}_Close_valve_when_lost_sensors_mode"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return self._device.get_close_valve_when_lost_sensors_mode()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_close_valve_when_lost_sensors_mode(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_close_valve_when_lost_sensors_mode(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:pipe-valve"


class LockButtons(CoordinatorEntity, SwitchEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = "Блокировка кнопок"
        self._attr_unique_id = f"{device.get_name()}_Lock_buttons"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        return self._device.get_lock_buttons()

    @property
    def available(self):
        return self._device.is_connected()

    async def async_turn_off(self, **kwargs):
        await self._device.set_lock_buttons(False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._device.set_lock_buttons(True)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:keyboard-off-outline" if self._device.get_lock_buttons() else "mdi:keyboard-close-outline"
