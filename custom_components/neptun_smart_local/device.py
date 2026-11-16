"""Модель устройства, радиодатчиков и счётчиков воды Neptun Smart."""

from __future__ import annotations

import asyncio
from asyncio.exceptions import InvalidStateError
import logging

from homeassistant.core import HomeAssistant
from pymodbus import ModbusException
from pymodbus.exceptions import ModbusIOException

from .const import (
    COUNTER_DECREASE_CONFIRM_READS,
    COUNTER_SLOTS,
    COUNTER_SPIKE_CONFIRM_READS,
    COUNTER_SPIKE_LITERS_THRESHOLD,
    MAX_WIRELESS_SENSORS,
)
from .hub import ModbusHub, registers_to_uint32, uint16_to_bits
from .registers import NeptunSmartRegisters

_LOGGER = logging.getLogger(__name__)

MAX_REASONABLE_LITERS = 0xFFFF0000


def _two_bits_to_uint(high_bit: int, low_bit: int) -> int:
    """Преобразует пару битов (MSB, LSB) в число 0..3."""
    return ((1 if high_bit else 0) << 1) | (1 if low_bit else 0)


class WirelessSensor:
    """Модель беспроводного датчика протечки Neptun Smart."""

    def __init__(
        self,
        hub: ModbusHub,
        io_lock: asyncio.Lock,
        address_config: int,
        address_value: int,
        config_raw: int,
        status_raw: int,
    ) -> None:
        self._hub = hub
        self._io_lock = io_lock
        self._address_config = address_config
        self._address_value = address_value
        self._config = 3
        self._battery_level = 0
        self._alert = False
        self._discharge = False
        self._lost_sensor = False
        self._signal_level = 0
        self.update_from_raw(config_raw, status_raw)

    def update_from_raw(self, config_raw: int, status_raw: int) -> None:
        """Разбирает сырые 16-битные регистры конфигурации и статуса радиодатчика."""
        self._config = int(config_raw) & 0xFFFF
        raw = int(status_raw) & 0xFFFF
        self._battery_level = min((raw >> 8) & 0xFF, 100)
        self._alert = bool(raw & 0x01)
        self._discharge = bool(raw & 0x02)
        self._lost_sensor = bool(raw & 0x04)
        self._signal_level = (raw >> 3) & 0x07

    def get_group_config(self) -> int:
        return self._config

    async def set_group_config_unlocked(self, config: int) -> None:
        await self._hub.write_holding_register(
            address=self._address_config, value=int(config)
        )
        self._config = int(config)

    async def set_group_config(self, config: int) -> None:
        async with self._io_lock:
            await self.set_group_config_unlocked(config)

    def get_battery_level(self) -> int:
        return self._battery_level

    def get_signal_level(self) -> int:
        return self._signal_level

    def get_alert_status(self) -> bool:
        return self._alert

    def get_lost_sensor_status(self) -> bool:
        return self._lost_sensor

    def get_discharge_status(self) -> bool:
        return self._discharge

    def get_address(self) -> int:
        return self._address_config


class Counter:
    """Модель счётчика воды с фильтрацией ложных нулей и одиночных сбоев."""

    def __init__(
        self,
        address: int,
        hub: ModbusHub,
        initial_raw_liters: int | None = None,
        config_raw: int | None = None,
    ) -> None:
        self._address = int(address)
        self._hub = hub
        self._slot_index = max(
            0, (self._address - NeptunSmartRegisters.first_counter) // 2
        )
        self._slot_number = (self._slot_index // 2) + 1
        self._channel_number = (self._slot_index % 2) + 1
        self._step_liters = self._extract_step_liters(config_raw)

        self._value_liters: int | None = None
        self._decrease_candidate: int | None = None
        self._decrease_count = 0
        self._spike_candidate: int | None = None
        self._spike_count = 0
        self._zero_filtered_logged = False
        self._rejected_zero_count = 0

        if initial_raw_liters is not None:
            self.update_raw_value(initial_raw_liters)

    @staticmethod
    def _extract_step_liters(config_raw: int | None) -> int:
        if config_raw is None:
            return 10
        step = (int(config_raw) >> 8) & 0xFF
        return step if step in (1, 10, 100) else 10

    def update_config_raw(self, config_raw: int) -> None:
        self._step_liters = self._extract_step_liters(config_raw)

    def restore_value_liters(self, restored_liters: int) -> None:
        """Восстанавливает последнее валидное показание из БД HA (RestoreSensor)."""
        if restored_liters <= 0 or restored_liters >= MAX_REASONABLE_LITERS:
            return
        if self._value_liters is None or self._value_liters == 0:
            if self._value_liters == 0:
                _LOGGER.warning(
                    "Счётчик %s (слот %s-%s): нулевое чтение при старте заменено "
                    "сохранённым в HA показанием %.3f м³",
                    self._address,
                    self._slot_number,
                    self._channel_number,
                    restored_liters / 1000,
                )
            self._value_liters = int(restored_liters)

    def update_raw_value(self, raw_liters: int | None) -> None:
        """Обновляет показание с защитой от нулей, откатов и спайков."""
        if raw_liters is None or raw_liters < 0:
            return
        raw = int(raw_liters)
        if raw >= MAX_REASONABLE_LITERS:
            return

        if self._value_liters is None:
            self._value_liters = raw
            return

        if raw == 0 and self._value_liters > 0:
            self._rejected_zero_count += 1
            self._decrease_candidate = None
            self._decrease_count = 0
            if not self._zero_filtered_logged:
                _LOGGER.warning(
                    "Счётчик %s (слот %s-%s) отдал 0 при показании %.3f м³ — "
                    "ложный сброс отфильтрован",
                    self._address,
                    self._slot_number,
                    self._channel_number,
                    self._value_liters / 1000,
                )
                self._zero_filtered_logged = True
            return

        if 0 < raw < self._value_liters:
            self._spike_candidate = None
            self._spike_count = 0
            if (
                self._decrease_candidate is not None
                and abs(raw - self._decrease_candidate) <= 50
            ):
                self._decrease_count += 1
            else:
                self._decrease_candidate = raw
                self._decrease_count = 1

            if self._decrease_count >= COUNTER_DECREASE_CONFIRM_READS:
                _LOGGER.info(
                    "Счётчик %s (слот %s-%s): принята коррекция %.3f -> %.3f м³",
                    self._address,
                    self._slot_number,
                    self._channel_number,
                    self._value_liters / 1000,
                    raw / 1000,
                )
                self._value_liters = raw
                self._decrease_candidate = None
                self._decrease_count = 0
                self._zero_filtered_logged = False
            return

        if (
            self._value_liters > 0
            and (raw - self._value_liters) > COUNTER_SPIKE_LITERS_THRESHOLD
        ):
            self._decrease_candidate = None
            self._decrease_count = 0
            if (
                self._spike_candidate is not None
                and abs(raw - self._spike_candidate) <= 500
            ):
                self._spike_count += 1
            else:
                self._spike_candidate = raw
                self._spike_count = 1
            if self._spike_count < COUNTER_SPIKE_CONFIRM_READS:
                return

        self._value_liters = raw
        self._decrease_candidate = None
        self._decrease_count = 0
        self._spike_candidate = None
        self._spike_count = 0
        self._zero_filtered_logged = False

    def get_value_liters(self) -> int | None:
        return self._value_liters

    def get_value_m3(self) -> float | None:
        return round(self._value_liters / 1000, 3) if self._value_liters is not None else None

    def get_value(self) -> int:
        return self._value_liters if self._value_liters is not None else 0

    def get_address(self) -> int:
        return self._address

    @property
    def slot_index(self) -> int:
        return self._slot_index

    @property
    def slot_number(self) -> int:
        return self._slot_number

    @property
    def channel_number(self) -> int:
        return self._channel_number

    @property
    def step_liters(self) -> int:
        return self._step_liters

    @property
    def rejected_zero_count(self) -> int:
        return self._rejected_zero_count


class NeptunSmart:
    """Логическая модель контроллера Neptun Smart."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host_ip: str,
        host_port: int | str,
        known_counters: list[int] | None = None,
    ) -> None:
        self._name = name
        self._hass = hass
        self._hub = ModbusHub(hass=hass, host=host_ip, port=host_port)
        self._io_lock = asyncio.Lock()
        self._known_counters = list(known_counters or [])

        self._line_type = [True, True, True, True, True]
        self._line_group = [3, 3, 3, 3, 3]
        self._line_status = [False, False, False, False, False]
        self.wireless_sensors: list[WirelessSensor] = []
        self.counters: list[Counter] = []
        self._wireless_sensors_connected = 0

        self._first_group_valve_is_open = False
        self._second_group_valve_is_open = False
        self._floor_washing_mode = False
        self._first_group_alarm = False
        self._second_group_alarm = False
        self._discharge_wireless_sensors = False
        self._lost_wireless_sensors = False
        self._connecting_wireless_sensors_mode = False
        self._dual_group_mode = False
        self._close_valve_when_loss_sensor = False
        self._lock_buttons = False
        self._switch_when_close_valve = 0
        self._switch_when_alert = 0

        self._config_bits: list[int] | None = None
        self._config_line_1_2_bits: list[int] | None = None
        self._config_line_3_4_bits: list[int] | None = None
        self._status_wired_line_bits: list[int] | None = None
        self._relay_config_bits: list[int] | None = None
        self._is_connected = False

    @property
    def host(self) -> str:
        return self._hub.host

    @property
    def port(self) -> int:
        return self._hub.port

    def get_counter_addresses(self) -> list[int]:
        return [c.get_address() for c in self.counters]

    async def init_sensors(self) -> None:
        """Подключение и первичное чтение конфигурации, радиодатчиков и счётчиков."""
        await self._hub.connect()

        async with self._io_lock:
            async with asyncio.timeout(15):
                base_regs = await self._hub.read_holding_registers(
                    NeptunSmartRegisters.module_config, 7
                )
                if not base_regs or len(base_regs) < 7:
                    raise ConnectionError(
                        f"Контроллер {self._name} не ответил на чтение базовых регистров"
                    )

                self._is_connected = True
                self._apply_base_registers(base_regs)

                if self._wireless_sensors_connected > 0:
                    configs = await self._hub.read_holding_registers(
                        NeptunSmartRegisters.first_wireless_sensor_config,
                        self._wireless_sensors_connected,
                    )
                    statuses = await self._hub.read_holding_registers(
                        NeptunSmartRegisters.first_wireless_sensor_status,
                        self._wireless_sensors_connected,
                    )
                    if configs and statuses:
                        for i in range(self._wireless_sensors_connected):
                            self.wireless_sensors.append(
                                WirelessSensor(
                                    hub=self._hub,
                                    io_lock=self._io_lock,
                                    address_config=NeptunSmartRegisters.first_wireless_sensor_config + i,
                                    address_value=NeptunSmartRegisters.first_wireless_sensor_status + i,
                                    config_raw=configs[i],
                                    status_raw=statuses[i],
                                )
                            )

                counter_configs = await self._hub.read_holding_registers(
                    NeptunSmartRegisters.first_counter_config, COUNTER_SLOTS
                )
                counter_values = await self._hub.read_holding_registers(
                    NeptunSmartRegisters.first_counter, COUNTER_SLOTS * 2
                )

                if counter_configs:
                    for i in range(COUNTER_SLOTS):
                        cfg_raw = counter_configs[i]
                        if cfg_raw & 0x01:
                            addr = NeptunSmartRegisters.first_counter + (i * 2)
                            init_liters = None
                            if counter_values and len(counter_values) >= (i * 2 + 2):
                                init_liters = registers_to_uint32(
                                    counter_values[i * 2], counter_values[i * 2 + 1]
                                )
                            self.counters.append(
                                Counter(addr, self._hub, init_liters, cfg_raw)
                            )
                elif self._known_counters:
                    for addr in self._known_counters:
                        offset = addr - NeptunSmartRegisters.first_counter
                        init_liters = None
                        if counter_values and 0 <= offset < len(counter_values) - 1:
                            init_liters = registers_to_uint32(
                                counter_values[offset], counter_values[offset + 1]
                            )
                        self.counters.append(Counter(addr, self._hub, init_liters))

    async def async_close(self) -> None:
        """Закрывает соединение с контроллером."""
        self._is_connected = False
        await self._hub.disconnect()

    def _apply_base_registers(self, registers: list[int]) -> None:
        self._apply_module_config_bits(uint16_to_bits(registers[0]))
        self._apply_line_1_2_bits(uint16_to_bits(registers[1]))
        self._apply_line_3_4_bits(uint16_to_bits(registers[2]))
        self._apply_wired_status_bits(uint16_to_bits(registers[3]))
        self._apply_relay_config_bits(uint16_to_bits(registers[4]))
        self._wireless_sensors_connected = min(
            int(registers[6]), MAX_WIRELESS_SENSORS
        )

    def _apply_module_config_bits(self, bits: list[int]) -> None:
        self._config_bits = bits
        self._first_group_valve_is_open = bool(bits[7])
        self._second_group_valve_is_open = bool(bits[6])
        self._floor_washing_mode = bool(bits[15])
        self._first_group_alarm = bool(bits[14])
        self._second_group_alarm = bool(bits[13])
        self._discharge_wireless_sensors = bool(bits[12])
        self._lost_wireless_sensors = bool(bits[11])
        self._connecting_wireless_sensors_mode = bool(bits[8])
        self._dual_group_mode = bool(bits[5])
        self._close_valve_when_loss_sensor = bool(bits[4])
        self._lock_buttons = bool(bits[3])

    def _apply_line_1_2_bits(self, bits: list[int]) -> None:
        self._config_line_1_2_bits = bits
        self._line_type[1] = bool(bits[5])
        self._line_type[2] = bool(bits[13])
        self._line_group[1] = _two_bits_to_uint(bits[6], bits[7])
        self._line_group[2] = _two_bits_to_uint(bits[14], bits[15])

    def _apply_line_3_4_bits(self, bits: list[int]) -> None:
        self._config_line_3_4_bits = bits
        self._line_type[3] = bool(bits[5])
        self._line_type[4] = bool(bits[13])
        self._line_group[3] = _two_bits_to_uint(bits[6], bits[7])
        self._line_group[4] = _two_bits_to_uint(bits[14], bits[15])

    def _apply_wired_status_bits(self, bits: list[int]) -> None:
        self._status_wired_line_bits = bits
        self._line_status[1] = bool(bits[15])
        self._line_status[2] = bool(bits[14])
        self._line_status[3] = bool(bits[13])
        self._line_status[4] = bool(bits[12])

    def _apply_relay_config_bits(self, bits: list[int]) -> None:
        self._relay_config_bits = bits
        self._switch_when_close_valve = _two_bits_to_uint(bits[12], bits[13])
        self._switch_when_alert = _two_bits_to_uint(bits[14], bits[15])

    async def _update_wireless_sensors_unlocked(self) -> None:
        count = len(self.wireless_sensors)
        if count == 0:
            return
        configs = await self._hub.read_holding_registers(
            NeptunSmartRegisters.first_wireless_sensor_config, count
        )
        statuses = await self._hub.read_holding_registers(
            NeptunSmartRegisters.first_wireless_sensor_status, count
        )
        if not configs or not statuses:
            return
        for i, sensor in enumerate(self.wireless_sensors):
            sensor.update_from_raw(configs[i], statuses[i])

    async def _update_counters_unlocked(self) -> None:
        if not self.counters:
            return
        values = await self._hub.read_holding_registers(
            NeptunSmartRegisters.first_counter, COUNTER_SLOTS * 2
        )
        if not values:
            return
        for counter in self.counters:
            offset = counter.get_address() - NeptunSmartRegisters.first_counter
            if 0 <= offset < len(values) - 1:
                raw_liters = registers_to_uint32(values[offset], values[offset + 1])
                counter.update_raw_value(raw_liters)

    async def update(self) -> bool:
        """Пакетный опрос контроллера за минимальное количество транзакций Modbus."""
        async with self._io_lock:
            try:
                async with asyncio.timeout(15):
                    if not self._hub.connected:
                        await self._hub.connect()

                    registers = await self._hub.read_holding_registers(
                        NeptunSmartRegisters.module_config, 7
                    )
                    if not registers or len(registers) < 7:
                        self._is_connected = False
                        return False

                    self._is_connected = True
                    self._apply_base_registers(registers)
                    await self._update_wireless_sensors_unlocked()
                    await self._update_counters_unlocked()
                    return True
            except asyncio.CancelledError:
                raise
            except (TimeoutError, ConnectionError, ModbusIOException, ModbusException, InvalidStateError) as err:
                _LOGGER.debug("Сбой опроса %s: %s", self._name, err)
                self._is_connected = False
                return False
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Непредвиденная ошибка опроса %s: %s", self._name, err)
                self._is_connected = False
                return False

    def get_discharge_wireless_sensors(self) -> bool:
        return self._discharge_wireless_sensors

    def get_lost_wireless_sensors(self) -> bool:
        return self._lost_wireless_sensors

    def get_number_of_connected_wireless_sensors(self) -> int:
        return self._wireless_sensors_connected

    def get_name(self) -> str:
        return self._name

    def get_first_group_alarm(self) -> bool:
        return self._first_group_alarm

    def get_second_group_alarm(self) -> bool:
        return self._second_group_alarm

    def get_first_group_valve_state(self) -> bool:
        return self._first_group_valve_is_open

    def get_second_group_valve_state(self) -> bool:
        return self._second_group_valve_is_open

    def get_floor_washing_mode(self) -> bool:
        return self._floor_washing_mode

    def get_connecting_wireless_sensors_mode(self) -> bool:
        return self._connecting_wireless_sensors_mode

    def get_dual_group_mode(self) -> bool:
        return self._dual_group_mode

    def is_connected(self) -> bool:
        return self._is_connected

    def get_close_valve_when_lost_sensors_mode(self) -> bool:
        return self._close_valve_when_loss_sensor

    def get_lock_buttons(self) -> bool:
        return self._lock_buttons

    def get_line_config_type(self, line_number: int) -> bool:
        return self._line_type[line_number]

    def get_line_group(self, line_number: int) -> int:
        return self._line_group[line_number]

    def get_line_status(self, line_number: int) -> bool:
        return self._line_status[line_number]

    def get_relay_config_valve(self) -> int:
        return int(self._switch_when_close_valve)

    def get_relay_config_alert(self) -> int:
        return int(self._switch_when_alert)

    async def _modify_module_config_unlocked(self, mutator) -> None:
        bits = await self._hub.read_holding_register_bits(
            NeptunSmartRegisters.module_config, 1
        )
        if bits is None or len(bits) < 16:
            raise RuntimeError("Не удалось прочитать конфигурацию модуля перед записью")
        mutator(bits)
        await self._hub.write_holding_register_bits(
            NeptunSmartRegisters.module_config, bits
        )
        self._apply_module_config_bits(bits)

    async def set_first_group_valve_state(self, state: bool) -> None:
        async with self._io_lock:
            def mutate(bits: list[int]) -> None:
                bits[7] = int(bool(state))
                if not bits[5]:
                    bits[6] = int(bool(state))

            await self._modify_module_config_unlocked(mutate)

    async def set_second_group_valve_state(self, state: bool) -> None:
        async with self._io_lock:
            await self._modify_module_config_unlocked(
                lambda bits: bits.__setitem__(6, int(bool(state)))
            )

    async def set_floor_washing_mode(self, state: bool) -> None:
        async with self._io_lock:
            await self._modify_module_config_unlocked(
                lambda bits: bits.__setitem__(15, int(bool(state)))
            )

    async def set_connecting_wireless_sensors_mode(self, state: bool) -> None:
        async with self._io_lock:
            await self._modify_module_config_unlocked(
                lambda bits: bits.__setitem__(8, int(bool(state)))
            )

    async def set_dual_group_mode(self, state: bool) -> None:
        async with self._io_lock:
            await self._modify_module_config_unlocked(
                lambda bits: bits.__setitem__(5, int(bool(state)))
            )
            if state:
                for i in (1, 2, 3, 4):
                    await self._set_line_group_unlocked(i, 3)
                for sensor in self.wireless_sensors:
                    await sensor.set_group_config_unlocked(3)

    async def set_close_valve_when_lost_sensors_mode(self, state: bool) -> None:
        async with self._io_lock:
            await self._modify_module_config_unlocked(
                lambda bits: bits.__setitem__(4, int(bool(state)))
            )

    async def set_lock_buttons(self, state: bool) -> None:
        async with self._io_lock:
            await self._modify_module_config_unlocked(
                lambda bits: bits.__setitem__(3, int(bool(state)))
            )

    @staticmethod
    def _line_register_and_type_indices(line_number: int) -> tuple[int, int, int]:
        if line_number == 1:
            return NeptunSmartRegisters.input_line_1_2_config, 4, 5
        if line_number == 2:
            return NeptunSmartRegisters.input_line_1_2_config, 12, 13
        if line_number == 3:
            return NeptunSmartRegisters.input_line_3_4_config, 4, 5
        if line_number == 4:
            return NeptunSmartRegisters.input_line_3_4_config, 12, 13
        raise ValueError(f"Неизвестный номер линии: {line_number}")

    @staticmethod
    def _line_register_and_group_indices(line_number: int) -> tuple[int, int, int]:
        if line_number == 1:
            return NeptunSmartRegisters.input_line_1_2_config, 6, 7
        if line_number == 2:
            return NeptunSmartRegisters.input_line_1_2_config, 14, 15
        if line_number == 3:
            return NeptunSmartRegisters.input_line_3_4_config, 6, 7
        if line_number == 4:
            return NeptunSmartRegisters.input_line_3_4_config, 14, 15
        raise ValueError(f"Неизвестный номер линии: {line_number}")

    def _apply_line_bits_for_register(self, address: int, bits: list[int]) -> None:
        if address == NeptunSmartRegisters.input_line_1_2_config:
            self._apply_line_1_2_bits(bits)
        else:
            self._apply_line_3_4_bits(bits)

    async def _read_line_bits_unlocked(self, address: int) -> list[int]:
        bits = await self._hub.read_holding_register_bits(address, 1)
        if bits is None or len(bits) < 16:
            raise RuntimeError(f"Не удалось прочитать регистр линий {address}")
        return bits

    async def set_line_type(self, line_number: int, state: bool) -> None:
        async with self._io_lock:
            address, high_idx, low_idx = self._line_register_and_type_indices(
                line_number
            )
            bits = await self._read_line_bits_unlocked(address)
            bits[high_idx] = 0
            bits[low_idx] = int(bool(state))
            await self._hub.write_holding_register_bits(address, bits)
            self._apply_line_bits_for_register(address, bits)

    async def _set_line_group_unlocked(self, line_number: int, state: int) -> None:
        address, high_idx, low_idx = self._line_register_and_group_indices(line_number)
        bits = await self._read_line_bits_unlocked(address)
        val = int(state) & 0x03 if state in (1, 2) else 3
        bits[high_idx] = (val >> 1) & 1
        bits[low_idx] = val & 1
        await self._hub.write_holding_register_bits(address, bits)
        self._apply_line_bits_for_register(address, bits)

    async def set_line_group(self, line_number: int, state: int) -> None:
        async with self._io_lock:
            await self._set_line_group_unlocked(line_number, state)

    @staticmethod
    def _encode_two_bit_value(
        bits: list[int], high_idx: int, low_idx: int, state: int
    ) -> None:
        value = int(state) & 0x03
        bits[high_idx] = (value >> 1) & 1
        bits[low_idx] = value & 1

    async def _modify_relay_config_unlocked(self, mutator) -> None:
        bits = await self._hub.read_holding_register_bits(
            NeptunSmartRegisters.relay_config, 1
        )
        if bits is None or len(bits) < 16:
            raise RuntimeError("Не удалось прочитать конфигурацию реле перед записью")
        mutator(bits)
        await self._hub.write_holding_register_bits(
            NeptunSmartRegisters.relay_config, bits
        )
        self._apply_relay_config_bits(bits)

    async def set_relay_config_valve(self, state: int) -> None:
        async with self._io_lock:
            await self._modify_relay_config_unlocked(
                lambda bits: self._encode_two_bit_value(bits, 12, 13, state)
            )

    async def set_relay_config_alert(self, state: int) -> None:
        async with self._io_lock:
            await self._modify_relay_config_unlocked(
                lambda bits: self._encode_two_bit_value(bits, 14, 15, state)
            )





