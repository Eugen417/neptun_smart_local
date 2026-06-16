from __future__ import annotations

from datetime import timedelta
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from . import NeptunSmart
from .const import DOMAIN
from .device import WirelessSensor

SCAN_INTERVAL = timedelta(seconds=5)

async def async_setup_entry(HomeAssistant, config_entry, async_add_entities):
    device: NeptunSmart = HomeAssistant.data[DOMAIN][config_entry.entry_id]
    selects = []
    
    for i in 1, 2, 3, 4:
        selects.append(LineTypeConfig(device=device, line_number=i))
        if device.get_dual_group_mode():
            selects.append(LineGroupConfig(device=device, line_number=i))
            
    selects.append(RelaySwitchWhenCloseValve(device))
    selects.append(RelaySwitchWhenAlert(device))
    
    for i in range(0, device.get_number_of_connected_wireless_sensors()):
        if device.get_dual_group_mode():
            selects.append(WirelessSensorGroupConfig(device, device.wireless_sensors[i], i+1))
            
    async_add_entities(selects, update_before_add=False)


class LineTypeConfig(SelectEntity):
    def __init__(self, device: NeptunSmart, line_number):
        self._device = device
        self._line_number = line_number
        self._state = self._device.get_line_config_type(line_number=line_number)      #True = button, False = sensor
        self._attr_unique_id = f"{device.get_name()}_Line_{self._line_number}_config"
        self._attr_name = f"Тип линии {self._line_number}"
        self._attr_entity_category = EntityCategory.CONFIG  
        if self._device.get_line_config_type(line_number=line_number):
            self._attr_current_option = "Кнопка"
        else:
            self._attr_current_option = "Датчик"

    async def async_select_option(self, option: str) -> None:
        if option == "Датчик":
            self._state = False
        else:
            self._state = True
        await self._device.set_line_type(self._line_number, self._state)

    @property
    def options(self) -> list[str]:
        return ["Датчик", "Кнопка"]

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    async def async_update(self) -> None:
        if self._device.get_line_config_type(self._line_number):
            self._attr_current_option = "Кнопка"
        else:
            self._attr_current_option = "Датчик"


class LineGroupConfig(SelectEntity):
    def __init__(self, device: NeptunSmart, line_number):
        self._device = device
        self._line_number = line_number
        self._state = self._device.get_line_group(line_number=line_number)
        self._attr_unique_id = f"{device.get_name()}_Line_{self._line_number}_group_ config"
        self._attr_name = f"Группа линии {self._line_number}"
        self._attr_entity_category = EntityCategory.CONFIG 
        self._state = self._device.get_line_group(line_number=line_number)
        
        if self._state == 1:
            self._attr_current_option = "Первая"
        elif self._state == 2:
            self._attr_current_option = "Вторая"
        else:
            self._attr_current_option = "Обе"

    async def async_select_option(self, option: str) -> None:
        if option == "Первая":
            self._state = 1
        elif option == "Вторая":
            self._state = 2
        else:
            self._state = 3
        await self._device.set_line_group(self._line_number, self._state)

    @property
    def options(self) -> list[str]:
        return ["Первая", "Вторая", "Обе"]

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    async def async_update(self) -> None:
        self._state = self._device.get_line_group(line_number=self._line_number)
        if self._state == 1:
            self._attr_current_option = "Первая"
        elif self._state == 2:
            self._attr_current_option = "Вторая"
        else:
            self._attr_current_option = "Обе"
        self._attr_available = self._device.get_dual_group_mode()


class RelaySwitchWhenCloseValve(SelectEntity):
    def __init__(self, device: NeptunSmart):
        self._device = device
        self._state = self._device.get_relay_config_valve() 
        self._attr_unique_id = f"{device.get_name()}_RelaySwitchWhenCloseValve_config"
        self._attr_name = f"Реле при закрытии кранов"
        self._attr_entity_category = EntityCategory.CONFIG  
        if self._state == 0:
            self._attr_current_option = "Не срабатывать"
        elif self._state == 1:
            self._attr_current_option = "Первая группа"
        elif self._state == 2:
            self._attr_current_option = "Вторая группа"
        else:
            self._attr_current_option = "Обе группы"

    async def async_select_option(self, option: str) -> None:
        if option == "Не срабатывать":
            self._state = 0
        elif option == "Первая группа":
            self._state = 1
        elif option == "Вторая группа":
            self._state = 2
        else:
            self._state = 3
        await self._device.set_relay_config_valve(self._state)

    @property
    def options(self) -> list[str]:
        return ["Не срабатывать", "Первая группа", "Вторая группа", "Обе группы"]

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    async def async_update(self) -> None:
        self._state = self._device.get_relay_config_valve()
        if self._state == 0:
            self._attr_current_option = "Не срабатывать"
        elif self._state == 1:
            self._attr_current_option = "Первая группа"
        elif self._state == 2:
            self._attr_current_option = "Вторая группа"
        else:
            self._attr_current_option = "Обе группы"


class RelaySwitchWhenAlert(SelectEntity):
    def __init__(self, device: NeptunSmart):
        self._device = device
        self._state = self._device.get_relay_config_alert() 
        self._attr_unique_id = f"{device.get_name()}_RelaySwitchAlert_config"
        self._attr_name = f"Реле при тревоге"
        self._attr_entity_category = EntityCategory.CONFIG  
        if self._state == 0:
            self._attr_current_option = "Не срабатывать"
        elif self._state == 1:
            self._attr_current_option = "Первая группа"
        elif self._state == 2:
            self._attr_current_option = "Вторая группа"
        else:
            self._attr_current_option = "Обе группы"

    async def async_select_option(self, option: str) -> None:
        if option == "Не срабатывать":
            self._state = 0
        elif option == "Первая группа":
            self._state = 1
        elif option == "Вторая группа":
            self._state = 2
        else:
            self._state = 3
        await self._device.set_relay_config_alert(self._state)

    @property
    def options(self) -> list[str]:
        return ["Не срабатывать", "Первая группа", "Вторая группа", "Обе группы"]

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    async def async_update(self) -> None:
        self._state = self._device.get_relay_config_alert()
        if self._state == 0:
            self._attr_current_option = "Не срабатывать"
        elif self._state == 1:
            self._attr_current_option = "Первая группа"
        elif self._state == 2:
            self._attr_current_option = "Вторая группа"
        else:
            self._attr_current_option = "Обе группы"


class WirelessSensorGroupConfig(SelectEntity):
    def __init__(self, device: NeptunSmart, sensor: WirelessSensor, sensor_number):
        self._device = device
        self._sensor = sensor
        self._sensor_number = sensor_number
        self._attr_unique_id = f"{device.get_name()}_WirelessSensor{self._sensor.get_address()}_group_ config"
        self._attr_name = f"Группа радиодатчика {self._sensor_number}"
        self._attr_entity_category = EntityCategory.CONFIG 
        self._state = self._sensor.get_group_config()
        if self._state == 1:
            self._attr_current_option = "Первая"
        elif self._state == 2:
            self._attr_current_option = "Вторая"
        else:
            self._attr_current_option = "Обе"

    async def async_select_option(self, option: str) -> None:
        if option == "Первая":
            self._state = 1
        elif option == "Вторая":
            self._state = 2
        else:
            self._state = 3
        await self._sensor.set_group_config(self._state)

    @property
    def options(self) -> list[str]:
        return ["Первая", "Вторая", "Обе"]

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    async def async_update(self) -> None:
        self._state = self._sensor.get_group_config()
        if self._state == 1:
            self._attr_current_option = "Первая"
        elif self._state == 2:
            self._attr_current_option = "Вторая"
        else:
            self._attr_current_option = "Обе"
