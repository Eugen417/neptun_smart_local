"""Асинхронный клиент Modbus TCP для контроллера Neptun Smart."""

from __future__ import annotations

import asyncio
import inspect
import logging

from homeassistant.core import HomeAssistant
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.framer import FramerType

from .const import DEFAULT_DEVICE_ID

_LOGGER = logging.getLogger(__name__)


def uint16_to_bits(value: int) -> list[int]:
    """Преобразует 16-битный регистр в список из 16 бит (индекс 0 = MSB бит 15)."""
    val = int(value) & 0xFFFF
    return [(val >> (15 - i)) & 1 for i in range(16)]


def bits_to_uint16(bits: list[int] | tuple[int, ...]) -> int:
    """Упаковывает список из 16 бит (индекс 0 = MSB) обратно в uint16."""
    value = 0
    for bit in bits:
        value = (value << 1) | (1 if bit else 0)
    return value & 0xFFFF


def registers_to_uint32(high: int, low: int) -> int:
    """Объединяет два 16-битных регистра (Big-Endian) в uint32."""
    return ((int(high) & 0xFFFF) << 16) | (int(low) & 0xFFFF)


class ModbusHub:
    """Обёртка над AsyncModbusTcpClient с сериализацией запросов."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int | str,
        device_id: int = DEFAULT_DEVICE_ID,
    ) -> None:
        self._hass = hass
        self._host = str(host).strip()
        self._port = int(port)
        self._device_id = int(device_id)
        self._client = self._create_client()
        self._is_connected = False
        self._request_semaphore = asyncio.Semaphore(1)
        self._unit_kwarg = self._detect_unit_kwarg()

    def _create_client(self) -> AsyncModbusTcpClient:
        return AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            framer=FramerType.SOCKET,
            retries=2,
            timeout=5,
            reconnect_delay=1,
        )

    def _detect_unit_kwarg(self) -> str:
        """Определяет имя параметра адреса ведомого для установленной версии pymodbus."""
        try:
            params = inspect.signature(self._client.read_holding_registers).parameters
            if "device_id" in params:
                return "device_id"
            if "slave" in params:
                return "slave"
        except Exception:  # noqa: BLE001
            pass
        return "device_id"

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def connected(self) -> bool:
        return bool(self._client and getattr(self._client, "connected", False))

    async def connect(self) -> None:
        """Устанавливает TCP-соединение с контроллером Neptun Smart."""
        try:
            if not self.connected:
                connected = await self._client.connect()
                if not connected and not self.connected:
                    raise ConnectionError(
                        f"Модуль {self._host}:{self._port} отклонил подключение"
                    )
            self._is_connected = True
        except asyncio.CancelledError:
            self._is_connected = False
            raise
        except Exception as err:
            self._is_connected = False
            _LOGGER.debug(
                "Ошибка подключения к Modbus %s:%s: %s", self._host, self._port, err
            )
            raise ConnectionError(
                f"Не удалось подключиться к {self._host}:{self._port}: {err}"
            ) from err

    async def disconnect(self) -> None:
        """Безопасно закрывает TCP-соединение и освобождает сокет модуля."""
        try:
            if self._client is not None:
                close_res = self._client.close()
                if asyncio.iscoroutine(close_res):
                    await close_res
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Игнорируем ошибку при закрытии Modbus-клиента: %s", err)
        finally:
            self._is_connected = False

    async def _ensure_connected(self) -> None:
        if not self.connected:
            await self.connect()

    async def read_holding_registers(
        self, address: int, count: int = 1
    ) -> list[int] | None:
        """Читает блок последовательных Holding-регистров."""
        async with self._request_semaphore:
            try:
                await self._ensure_connected()
                kwargs = {self._unit_kwarg: self._device_id}
                result = await self._client.read_holding_registers(
                    address, count=count, **kwargs
                )
                if result.isError():
                    _LOGGER.debug(
                        "Ошибка Modbus при чтении регистров %s+%s: %s",
                        address,
                        count,
                        result,
                    )
                    return None
                if result.registers is not None and len(result.registers) >= count:
                    return [int(r) & 0xFFFF for r in result.registers[:count]]
                return None
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Сбой чтения регистров %s+%s (%s:%s): %s",
                    address,
                    count,
                    self._host,
                    self._port,
                    err,
                )
                await self.disconnect()
                return None

    async def read_holding_register_uint16(
        self, address: int, count: int = 1
    ) -> int | None:
        registers = await self.read_holding_registers(address, 1)
        return registers[0] if registers else None

    async def read_holding_register_uint32(
        self, address: int, count: int = 2
    ) -> int | None:
        registers = await self.read_holding_registers(address, 2)
        if registers and len(registers) >= 2:
            return registers_to_uint32(registers[0], registers[1])
        return None

    async def read_holding_register_bits(
        self, address: int, count: int = 1
    ) -> list[int] | None:
        registers = await self.read_holding_registers(address, 1)
        if registers:
            return uint16_to_bits(registers[0])
        return None

    async def write_holding_register_bits(
        self, address: int, bits: list[int]
    ) -> None:
        if bits is None or len(bits) != 16:
            raise ValueError(
                f"Для записи регистра {address} требуется 16 бит, получено: "
                f"{len(bits) if bits is not None else None}"
            )
        await self.write_holding_register(address, bits_to_uint16(bits))

    async def write_holding_register(self, address: int, value: int) -> None:
        async with self._request_semaphore:
            try:
                await self._ensure_connected()
                kwargs = {self._unit_kwarg: self._device_id}
                result = await self._client.write_register(
                    address, int(value) & 0xFFFF, **kwargs
                )
                if result.isError():
                    raise IOError(f"Ошибка записи Modbus в регистр {address}: {result}")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.warning(
                    "Ошибка при записи значения %s в регистр %s: %s",
                    value,
                    address,
                    err,
                )
                raise


modbus_hub = ModbusHub

