"""Константы интеграции Neptun Smart Local."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "neptun_smart_local"

CONF_NAME = "name"
CONF_HOST_IP = "host_ip"
CONF_HOST_PORT = "host_port"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_KNOWN_COUNTERS = "known_counters"

DEFAULT_NAME = "Neptun_Smart"
DEFAULT_PORT = 503
DEFAULT_DEVICE_ID = 240
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 120

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

MAX_WIRELESS_SENSORS = 50
COUNTER_SLOTS = 8

# Параметры фильтрации ложных выбросов и нулей счётчиков воды
COUNTER_DECREASE_CONFIRM_READS = 6
COUNTER_SPIKE_LITERS_THRESHOLD = 100_000  # 100 м³ за одно чтение требует подтверждения
COUNTER_SPIKE_CONFIRM_READS = 3
