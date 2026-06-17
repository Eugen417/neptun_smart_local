from __future__ import annotations

from collections import namedtuple
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (UnitOfVolume, PERCENTAGE)
from .const import DOMAIN
from .device import NeptunSmart, WirelessSensor, Counter


async def async_setup_entry(HomeAssistant, config_entry, async_add_entities):
    device: NeptunSmart = HomeAssistant.data[DOMAIN][config_entry.entry_id]
    sensors = []
    sensors.append(WirelessSensorsConnected(device=device))
    for i in range(0, device.get_number_of_connected_wireless_sensors()):
        sensors.append(WirelessSensorsBatteryLevel(device, i+1, device.wireless_sensors[i]))
        sensors.append(WirelessSensorsSignalLevel(device, i+1, device.wireless_sensors[i]))
    for counter in device.counters:
        sensors.append(CounterSensor(device, counter))
    async_add_entities(sensors, update_before_add=False)


class WirelessSensorsConnected(CoordinatorEntity, SensorEntity):
    def __init__(self, device: NeptunSmart):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = f"{device.get_name()}_Wireless_sensors_connected"
        self._attr_name = "Подключено радиодатчиков"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._device.get_number_of_connected_wireless_sensors()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:sun-wireless-outline"


class WirelessSensorsBatteryLevel(CoordinatorEntity, SensorEntity):
    def __init__(self, device: NeptunSmart, sensor_number, sensor: WirelessSensor):
        super().__init__(device.coordinator)
        self._device = device
        self._sensor_number = sensor_number
        self._sensor = sensor
        self._attr_unique_id = f"{device.get_name()}_WirelessSensors{sensor_number}BatteryLevel"
        self._attr_name = f"Заряд батареи радиодатчика {sensor_number}"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._sensor.get_battery_level()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:battery-high"


class WirelessSensorsSignalLevel(CoordinatorEntity, SensorEntity):
    def __init__(self, device: NeptunSmart, sensor_number, sensor: WirelessSensor):
        super().__init__(device.coordinator)
        self._device = device
        self._sensor_number = sensor_number
        self._sensor = sensor
        self._attr_unique_id = f"{device.get_name()}_WirelessSensors{sensor_number}SignalLevel"
        self._attr_name = f"Уровень сигнала радиодатчика {sensor_number}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._sensor.get_signal_level()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:signal"


class CounterSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, device: NeptunSmart, counter: Counter):
        super().__init__(device.coordinator)
        self._device = device
        self._counter = counter
        self._attr_unique_id = f"{device.get_name()}_Counter{counter.get_address()}"
        self._attr_name = f"Счетчик воды {counter.get_address()}"
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        return self._counter.get_value() / 1000

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._device.get_name())}}

    @property
    def icon(self):
        return "mdi:counter"
