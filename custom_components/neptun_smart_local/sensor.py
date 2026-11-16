"""Сенсоры контроллера Neptun Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NeptunSmartCoordinator
from .device import Counter, WirelessSensor
from .entity import NeptunEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Регистрация сенсоров Neptun Smart."""
    coordinator: NeptunSmartCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    sensors: list[SensorEntity] = [WirelessSensorsConnected(coordinator)]
    for idx, wireless in enumerate(device.wireless_sensors, start=1):
        sensors.append(WirelessSensorsBatteryLevel(coordinator, idx, wireless))
        sensors.append(WirelessSensorsSignalLevel(coordinator, idx, wireless))

    for counter in device.counters:
        sensors.append(CounterSensor(coordinator, counter))

    async_add_entities(sensors)


class WirelessSensorsConnected(NeptunEntity, SensorEntity):
    """Количество привязанных беспроводных датчиков."""

    _attr_translation_key = "wireless_sensors_connected"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-wireless-outline"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_Wireless_sensors_connected"

    @property
    def native_value(self) -> int:
        return self._device.get_number_of_connected_wireless_sensors()


class WirelessSensorsBatteryLevel(NeptunEntity, SensorEntity):
    """Заряд батареи беспроводного датчика."""

    _attr_translation_key = "wireless_sensor_battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: NeptunSmartCoordinator,
        sensor_number: int,
        sensor: WirelessSensor,
    ) -> None:
        super().__init__(coordinator)
        self._sensor = sensor
        self._attr_unique_id = (
            f"{self._device.get_name()}_WirelessSensors{sensor_number}BatteryLevel"
        )
        self._attr_translation_placeholders = {"number": str(sensor_number)}

    @property
    def native_value(self) -> int:
        return self._sensor.get_battery_level()


class WirelessSensorsSignalLevel(NeptunEntity, SensorEntity):
    """Уровень радиосигнала беспроводного датчика."""

    _attr_translation_key = "wireless_sensor_signal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:signal"

    def __init__(
        self,
        coordinator: NeptunSmartCoordinator,
        sensor_number: int,
        sensor: WirelessSensor,
    ) -> None:
        super().__init__(coordinator)
        self._sensor = sensor
        self._attr_unique_id = (
            f"{self._device.get_name()}_WirelessSensors{sensor_number}SignalLevel"
        )
        self._attr_translation_placeholders = {"number": str(sensor_number)}

    @property
    def native_value(self) -> int:
        return self._sensor.get_signal_level()


class CounterSensor(NeptunEntity, RestoreSensor):
    """Сенсор импульсного счётчика воды с защитой от нулевых провалов при рестарте."""

    _attr_translation_key = "water_counter"
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_suggested_display_precision = 3
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:counter"

    def __init__(
        self, coordinator: NeptunSmartCoordinator, counter: Counter
    ) -> None:
        super().__init__(coordinator)
        self._counter = counter
        self._attr_unique_id = (
            f"{self._device.get_name()}_Counter{counter.get_address()}"
        )
        self._attr_translation_placeholders = {
            "slot": str(counter.slot_number),
            "channel": str(counter.channel_number),
            "address": str(counter.get_address()),
        }

    async def async_added_to_hass(self) -> None:
        """Восстанавливает последнее ненулевое показание из базы HA при перезагрузке."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and last_data.native_value is not None:
            try:
                val = float(last_data.native_value)
                if last_data.native_unit_of_measurement == UnitOfVolume.LITERS:
                    restored_liters = round(val)
                else:
                    restored_liters = round(val * 1000)
                self._counter.restore_value_liters(restored_liters)
            except (TypeError, ValueError):
                pass

    @property
    def available(self) -> bool:
        return super().available and self._counter.get_value_liters() is not None

    @property
    def native_value(self) -> float | None:
        return self._counter.get_value_m3()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "slot": self._counter.slot_number,
            "channel": self._counter.channel_number,
            "modbus_register": self._counter.get_address(),
            "pulse_step_liters": self._counter.step_liters,
            "filtered_zero_glitches": self._counter.rejected_zero_count,
        }

