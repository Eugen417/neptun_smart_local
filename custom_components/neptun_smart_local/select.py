"""Выбор настроек проводных линий, радиодатчиков и реле Neptun Smart."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NeptunSmartCoordinator
from .device import WirelessSensor
from .entity import NeptunEntity

LINE_TYPE_OPTIONS = ["sensor", "button"]
GROUP_OPTIONS = ["group_1", "group_2", "both"]
RELAY_OPTIONS = ["none", "group_1", "group_2", "both"]

GROUP_TO_INT = {"group_1": 1, "group_2": 2, "both": 3}
INT_TO_GROUP = {1: "group_1", 2: "group_2", 3: "both"}

RELAY_TO_INT = {"none": 0, "group_1": 1, "group_2": 2, "both": 3}
INT_TO_RELAY = {0: "none", 1: "group_1", 2: "group_2", 3: "both"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Регистрация элементов выбора (Select) Neptun Smart."""
    coordinator: NeptunSmartCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    selects: list[SelectEntity] = []
    for line_num in (1, 2, 3, 4):
        selects.append(LineTypeConfig(coordinator, line_number=line_num))
        if device.get_dual_group_mode():
            selects.append(LineGroupConfig(coordinator, line_number=line_num))

    selects.append(RelaySwitchWhenCloseValve(coordinator))
    selects.append(RelaySwitchWhenAlert(coordinator))

    if device.get_dual_group_mode():
        for idx, wireless in enumerate(device.wireless_sensors, start=1):
            selects.append(WirelessSensorGroupConfig(coordinator, wireless, idx))

    async_add_entities(selects)


class LineTypeConfig(NeptunEntity, SelectEntity):
    """Настройка типа проводной линии (Датчик / Кнопка)."""

    _attr_translation_key = "line_type"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = LINE_TYPE_OPTIONS
    _attr_icon = "mdi:electric-switch"

    def __init__(
        self, coordinator: NeptunSmartCoordinator, line_number: int
    ) -> None:
        super().__init__(coordinator)
        self._line_number = line_number
        self._attr_unique_id = (
            f"{self._device.get_name()}_Line_{line_number}_config"
        )
        self._attr_translation_placeholders = {"number": str(line_number)}

    @property
    def current_option(self) -> str:
        return (
            "button"
            if self._device.get_line_config_type(self._line_number)
            else "sensor"
        )

    async def async_select_option(self, option: str) -> None:
        await self._device.set_line_type(self._line_number, option == "button")
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class LineGroupConfig(NeptunEntity, SelectEntity):
    """Привязка проводной линии к группе кранов."""

    _attr_translation_key = "line_group"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = GROUP_OPTIONS
    _attr_icon = "mdi:source-branch"

    def __init__(
        self, coordinator: NeptunSmartCoordinator, line_number: int
    ) -> None:
        super().__init__(coordinator)
        self._line_number = line_number
        # Сохраняем оригинальный unique_id (с пробелом перед config) для обратной совместимости
        self._attr_unique_id = (
            f"{self._device.get_name()}_Line_{line_number}_group_ config"
        )
        self._attr_translation_placeholders = {"number": str(line_number)}

    @property
    def current_option(self) -> str:
        return INT_TO_GROUP.get(
            self._device.get_line_group(line_number=self._line_number), "both"
        )

    @property
    def available(self) -> bool:
        return super().available and self._device.get_dual_group_mode()

    async def async_select_option(self, option: str) -> None:
        await self._device.set_line_group(
            self._line_number, GROUP_TO_INT.get(option, 3)
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class RelaySwitchWhenCloseValve(NeptunEntity, SelectEntity):
    """Срабатывание реле при закрытии кранов."""

    _attr_translation_key = "relay_on_valve_close"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = RELAY_OPTIONS
    _attr_icon = "mdi:electric-switch-closed"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_RelaySwitchWhenCloseValve_config"
        )

    @property
    def current_option(self) -> str:
        return INT_TO_RELAY.get(self._device.get_relay_config_valve(), "none")

    async def async_select_option(self, option: str) -> None:
        await self._device.set_relay_config_valve(RELAY_TO_INT.get(option, 0))
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class RelaySwitchWhenAlert(NeptunEntity, SelectEntity):
    """Срабатывание реле при тревоге протечки."""

    _attr_translation_key = "relay_on_alarm"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = RELAY_OPTIONS
    _attr_icon = "mdi:alarm-light-outline"

    def __init__(self, coordinator: NeptunSmartCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{self._device.get_name()}_RelaySwitchAlert_config"
        )

    @property
    def current_option(self) -> str:
        return INT_TO_RELAY.get(self._device.get_relay_config_alert(), "none")

    async def async_select_option(self, option: str) -> None:
        await self._device.set_relay_config_alert(RELAY_TO_INT.get(option, 0))
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class WirelessSensorGroupConfig(NeptunEntity, SelectEntity):
    """Привязка беспроводного датчика к группе кранов."""

    _attr_translation_key = "wireless_sensor_group"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = GROUP_OPTIONS
    _attr_icon = "mdi:access-point-network"

    def __init__(
        self,
        coordinator: NeptunSmartCoordinator,
        sensor: WirelessSensor,
        sensor_number: int,
    ) -> None:
        super().__init__(coordinator)
        self._sensor = sensor
        # Сохраняем оригинальный unique_id (с пробелом перед config) для обратной совместимости
        self._attr_unique_id = (
            f"{self._device.get_name()}_WirelessSensor{sensor.get_address()}_group_ config"
        )
        self._attr_translation_placeholders = {"number": str(sensor_number)}

    @property
    def current_option(self) -> str:
        return INT_TO_GROUP.get(self._sensor.get_group_config(), "both")

    @property
    def available(self) -> bool:
        return super().available and self._device.get_dual_group_mode()

    async def async_select_option(self, option: str) -> None:
        await self._sensor.set_group_config(GROUP_TO_INT.get(option, 3))
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

