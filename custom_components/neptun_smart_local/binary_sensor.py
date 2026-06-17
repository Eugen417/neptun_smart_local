from __future__ import annotations

from datetime import timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from . import NeptunSmart
from .device import WirelessSensor

async def async_setup_entry(HomeAssistant, config_entry, async_add_entities):
    device: NeptunSmart = HomeAssistant.data[DOMAIN][config_entry.entry_id]
    binary_sensors = []
    binary_sensors.append(MainModule(device=device))
    binary_sensors.append(FirstGroupModuleAlert(device))
    
    if device.get_dual_group_mode():
        binary_sensors.append(SecondGroupModuleAlert(device))
        
    binary_sensors.append(DischargeWirelessSensors(device))
    binary_sensors.append(LostWirelessSensors(device))
    
    for i in 1, 2, 3, 4:
        binary_sensors.append(WiredLineAlertStatus(device=device, line_number=i))
        
    for i in range(0, device.get_number_of_connected_wireless_sensors()):
        binary_sensors.append(WirelessSensorAlertStatus(device, i+1, device.wireless_sensors[i]))
        binary_sensors.append(WirelessSensorDischargeStatus(device, i + 1, device.wireless_sensors[i]))
        binary_sensors.append(WirelessSensorLostStatus(device, i + 1, device.wireless_sensors[i]))
        
    async_add_entities(binary_sensors, update_before_add=False)


class MainModule(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = self._device.get_name()
        self._attr_name = self._device.get_name()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device.get_name())},
            "name": self._device.get_name(),
            "model": "Neptun Smart",
            "manufacturer": "Teploluxe",
            "sw_version": "1.2.2",
        }

    @property
    def icon(self):
        return "mdi:water-pump"

    @property
    def is_on(self) -> bool:
        return self._device.get_first_group_alarm() or self._device.get_second_group_alarm()


class FirstGroupModuleAlert(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = f"{device.get_name()}_first_group_alarm_module_alert"
        self._attr_name = "Протечка 1 группы"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:water"

    @property
    def is_on(self) -> bool:
        return self._device.get_first_group_alarm()


class SecondGroupModuleAlert(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = f"{device.get_name()}_second_group_alarm_module_alert"
        self._attr_name = "Протечка 2 группы"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:water"

    @property
    def is_on(self) -> bool:
        return self._device.get_second_group_alarm()

    @property
    def available(self) -> bool:
        return self._device.get_dual_group_mode() and self._device.is_connected()


class DischargeWirelessSensors(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = f"{device.get_name()}_discharge_wireless_sensors"
        self._attr_name = "Разряд батареи радиодатчиков"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:battery"

    @property
    def is_on(self) -> bool:
        return self._device.get_discharge_wireless_sensors()


class LostWirelessSensors(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = f"{device.get_name()}_lost_wireless_sensors"
        self._attr_name = "Потеря связи с радиодатчиками"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:wifi"

    @property
    def is_on(self) -> bool:
        return self._device.get_lost_wireless_sensors()


class WiredLineAlertStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, device: NeptunSmart, line_number):
        super().__init__(device.coordinator)
        self._device = device
        self._line_number = line_number
        self._attr_unique_id = f"{device.get_name()}_WiredAlertStatus_line{line_number}"
        self._attr_name = f"Протечка проводной линии {line_number}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:water"

    @property
    def is_on(self) -> bool:
        return self._device.get_line_status(line_number=self._line_number)


class WirelessSensorAlertStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, device: NeptunSmart, sensor_number, sensor: WirelessSensor):
        super().__init__(device.coordinator)
        self._device = device
        self._sensor_number = sensor_number
        self._sensor = sensor
        self._attr_unique_id = f"{device.get_name()}_WirelessAlertStatus_sensor{sensor_number}"
        self._attr_name = f"Протечка радиодатчика {sensor_number}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:water"

    @property
    def is_on(self) -> bool:
        return self._sensor.get_alert_status()


class WirelessSensorDischargeStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, device: NeptunSmart, sensor_number, sensor: WirelessSensor):
        super().__init__(device.coordinator)
        self._device = device
        self._sensor_number = sensor_number
        self._sensor = sensor
        self._attr_unique_id = f"{device.get_name()}_WirelessDischargeStatus_sensor{sensor_number}"
        self._attr_name = f"Разряд батареи радиодатчика {sensor_number}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:battery"

    @property
    def is_on(self) -> bool:
        return self._sensor.get_discharge_status()


class WirelessSensorLostStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, device: NeptunSmart, sensor_number, sensor: WirelessSensor):
        super().__init__(device.coordinator)
        self._device = device
        self._sensor_number = sensor_number
        self._sensor = sensor
        self._attr_unique_id = f"{device.get_name()}_WirelessLostStatus_sensor{sensor_number}"
        self._attr_name = f"Потеря связи с радиодатчиком {sensor_number}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:wifi"

    @property
    def is_on(self) -> bool:
        return self._sensor.get_lost_sensor_status()
