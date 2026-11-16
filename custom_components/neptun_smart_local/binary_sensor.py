"""Бинарные сенсоры контроллера Neptun Smart (протечки и статусы радиодатчиков)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NeptunSmartCoordinator
from .device import WirelessSensor
from .entity import NeptunEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Регистрация бинарных сенсоров Neptun Smart."""
    coordinator: NeptunSmartCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    entities: list[BinarySensorEntity] = [
        MainModule(coordinator),
        FirstGroupModuleAlert(coordinator),
    ]
    if device.get_dual_group_mode():
        entities.append(SecondGroupModuleAlert(coordinator))

    entities.extend(
        [
            DischargeWirelessSensors(coordinator),
            LostWirelessSensors(coordinator),
        ]
    )

    for line_num in (1, 2, 3, 4):
        entities.append(WiredLineAlertStatus(coordinator, line_number=line_num))

    for idx, wireless in enumerate(device.wireless_sensors, start=1):
        entities.append(WirelessSensorAlertStatus(coordinator, idx, wireless))
        entities.append(WirelessSensorDischargeStatus(coordinator, idx, wireless))
        entities.append(WirelessSensorLostStatus(coordinator, idx, wireless))

    async_add_entities(entities)


class MainModule(NeptunEntity, BinarySensorEntity):
    """Общая тревога контроллера Neptun Smart."""

    _attr_translation_key = "system_alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-pump"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = self._device.get_name()

    @property
    def is_on(self) -> bool:
        return bool(
            self._device.get_first_group_alarm()
            or self._device.get_second_group_alarm()
        )


class FirstGroupModuleAlert(NeptunEntity, BinarySensorEntity):
    """Тревога протечки 1 группы."""

    _attr_translation_key = "first_group_leak"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_first_group_alarm_module_alert"
        )

    @property
    def is_on(self) -> bool:
        return self._device.get_first_group_alarm()


class SecondGroupModuleAlert(NeptunEntity, BinarySensorEntity):
    """Тревога протечки 2 группы."""

    _attr_translation_key = "second_group_leak"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_second_group_alarm_module_alert"
        )

    @property
    def is_on(self) -> bool:
        return self._device.get_second_group_alarm()

    @property
    def available(self) -> bool:
        return super().available and self._device.get_dual_group_mode()


class DischargeWirelessSensors(NeptunEntity, BinarySensorEntity):
    """Общий флаг разряда батарей радиодатчиков."""

    _attr_translation_key = "wireless_sensors_battery_low"
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_discharge_wireless_sensors"
        )

    @property
    def is_on(self) -> bool:
        return self._device.get_discharge_wireless_sensors()


class LostWirelessSensors(NeptunEntity, BinarySensorEntity):
    """Общий флаг потери связи с радиодатчиками."""

    _attr_translation_key = "wireless_sensors_lost"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:wifi-alert"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device.get_name()}_lost_wireless_sensors"

    @property
    def is_on(self) -> bool:
        return self._device.get_lost_wireless_sensors()


class WiredLineAlertStatus(NeptunEntity, BinarySensorEntity):
    """Статус протечки проводной линии 1..4."""

    _attr_translation_key = "wired_line_leak"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(
        self, coordinator: NeptunSmartCoordinator, line_number: int
    ) -> None:
        super().__init__(coordinator)
        self._line_number = line_number
        self._attr_unique_id = (
            f"{self._device.get_name()}_WiredAlertStatus_line{line_number}"
        )
        self._attr_translation_placeholders = {"number": str(line_number)}

    @property
    def is_on(self) -> bool:
        return self._device.get_line_status(line_number=self._line_number)


class WirelessSensorAlertStatus(NeptunEntity, BinarySensorEntity):
    """Статус протечки беспроводного датчика."""

    _attr_translation_key = "wireless_sensor_leak"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(
        self,
        coordinator: NeptunSmartCoordinator,
        sensor_number: int,
        sensor: WirelessSensor,
    ) -> None:
        super().__init__(coordinator)
        self._sensor = sensor
        self._attr_unique_id = (
            f"{self._device.get_name()}_WirelessAlertStatus_sensor{sensor_number}"
        )
        self._attr_translation_placeholders = {"number": str(sensor_number)}

    @property
    def is_on(self) -> bool:
        return self._sensor.get_alert_status()


class WirelessSensorDischargeStatus(NeptunEntity, BinarySensorEntity):
    """Статус разряда батареи беспроводного датчика."""

    _attr_translation_key = "wireless_sensor_battery_low"
    _attr_device_class = BinarySensorDeviceClass.BATTERY
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
            f"{self._device.get_name()}_WirelessDischargeStatus_sensor{sensor_number}"
        )
        self._attr_translation_placeholders = {"number": str(sensor_number)}

    @property
    def is_on(self) -> bool:
        return self._sensor.get_discharge_status()


class WirelessSensorLostStatus(NeptunEntity, BinarySensorEntity):
    """Статус потери связи с беспроводным датчиком."""

    _attr_translation_key = "wireless_sensor_lost"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:wifi-off"

    def __init__(
        self,
        coordinator: NeptunSmartCoordinator,
        sensor_number: int,
        sensor: WirelessSensor,
    ) -> None:
        super().__init__(coordinator)
        self._sensor = sensor
        self._attr_unique_id = (
            f"{self._device.get_name()}_WirelessLostStatus_sensor{sensor_number}"
        )
        self._attr_translation_placeholders = {"number": str(sensor_number)}

    @property
    def is_on(self) -> bool:
        return self._sensor.get_lost_sensor_status()

