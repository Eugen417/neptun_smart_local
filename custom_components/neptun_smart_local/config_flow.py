"""ConfigFlow и OptionsFlow для интеграции Neptun Smart Local."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_HOST_IP,
    CONF_HOST_PORT,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .hub import ModbusHub
from .registers import NeptunSmartRegisters


async def async_validate_connection(
    hass: HomeAssistant, host_ip: str, host_port: int
) -> None:
    """Проверяет доступность контроллера по Modbus TCP."""
    hub = ModbusHub(hass=hass, host=host_ip, port=host_port)
    try:
        async with asyncio.timeout(8):
            await hub.connect()
            regs = await hub.read_holding_registers(
                NeptunSmartRegisters.module_config, 1
            )
            if not regs:
                raise ConnectionError("Empty Modbus response")
    finally:
        await hub.disconnect()


class NeptunSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Мастер первоначальной настройки Neptun Smart."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self.async_step_tcp(user_input)

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input.get(CONF_NAME, DEFAULT_NAME)).strip() or DEFAULT_NAME
            host_ip = str(user_input.get(CONF_HOST_IP, "")).strip()
            try:
                host_port = int(user_input.get(CONF_HOST_PORT, DEFAULT_PORT))
            except (TypeError, ValueError):
                host_port = -1
            scan_interval = int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )

            if not host_ip:
                errors[CONF_HOST_IP] = "invalid_host"
            elif not (1 <= host_port <= 65535):
                errors[CONF_HOST_PORT] = "invalid_port"
            else:
                await self.async_set_unique_id(f"{host_ip.lower()}:{host_port}")
                self._abort_if_unique_id_configured()
                try:
                    await async_validate_connection(self.hass, host_ip, host_port)
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_HOST_IP: host_ip,
                        CONF_HOST_PORT: host_port,
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST_IP): str,
                vol.Required(CONF_HOST_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )
        return self.async_show_form(
            step_id="tcp", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NeptunSmartOptionsFlow:
        return NeptunSmartOptionsFlow()


class NeptunSmartOptionsFlow(config_entries.OptionsFlow):
    """Настройка IP-адреса, порта и интервала опроса без удаления интеграции."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        current_host = str(
            self.config_entry.options.get(
                CONF_HOST_IP, self.config_entry.data.get(CONF_HOST_IP, "")
            )
        )
        current_port = int(
            self.config_entry.options.get(
                CONF_HOST_PORT,
                self.config_entry.data.get(CONF_HOST_PORT, DEFAULT_PORT),
            )
        )
        current_interval = int(
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )

        if user_input is not None:
            host_ip = str(user_input.get(CONF_HOST_IP, "")).strip()
            try:
                host_port = int(user_input.get(CONF_HOST_PORT, DEFAULT_PORT))
            except (TypeError, ValueError):
                host_port = -1
            scan_interval = int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )

            if not host_ip:
                errors[CONF_HOST_IP] = "invalid_host"
            elif not (1 <= host_port <= 65535):
                errors[CONF_HOST_PORT] = "invalid_port"
            elif host_ip != current_host or host_port != current_port:
                try:
                    await async_validate_connection(self.hass, host_ip, host_port)
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"

            if not errors:
                new_options = {
                    **self.config_entry.options,
                    CONF_HOST_IP: host_ip,
                    CONF_HOST_PORT: host_port,
                    CONF_SCAN_INTERVAL: scan_interval,
                }
                return self.async_create_entry(title="", data=new_options)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST_IP, default=current_host): str,
                vol.Required(CONF_HOST_PORT, default=current_port): vol.Coerce(int),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )

