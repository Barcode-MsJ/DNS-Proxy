"""Configuration loading and validation for the DNS Proxy project."""
from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when a required project configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    base_dir: Path
    upstream_ip: str
    upstream_port: int
    upstream_timeout_sec: float
    sinkhole_ip: str
    proxy_ip: str
    local_ttl: int
    ad_list_file: Path
    sanction_list_file: Path
    cache_enabled: bool
    cache_max_entries: int | None = None
    real_dns_enabled: bool = False

    @property
    def log_file(self) -> Path:
        # B4 explicitly specifies the fixed filename log.txt.
        return self.base_dir / "log.txt"


def _parse_bool(key: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ConfigError(f"Invalid value for {key}: expected true or false")
    return normalized == "true"


def _parse_int(key: str, value: str, minimum: int, maximum: int | None = None) -> int:
    try:
        parsed = int(value.strip())
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid value for {key}: expected an integer") from exc
    if parsed < minimum or (maximum is not None and parsed > maximum):
        limit = f" between {minimum} and {maximum}" if maximum is not None else f" >= {minimum}"
        raise ConfigError(f"Invalid value for {key}: expected{limit}")
    return parsed


def _parse_ipv4(key: str, value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value.strip()))
    except ipaddress.AddressValueError as exc:
        raise ConfigError(f"Invalid value for {key}: expected an IPv4 address") from exc


def load_config(base_dir: str | Path | None = None, filename: str = "config.txt") -> Config:
    root = Path(base_dir or Path(__file__).resolve().parents[1]).resolve()
    config_path = root / filename
    if not config_path.is_file():
        raise ConfigError(f"{filename} not found in {root}")

    values: dict[str, str] = {}
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"Cannot read {filename}: {exc}") from exc

    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"Invalid config line {number}: expected key=value")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise ConfigError(f"Invalid config line {number}: key and value must not be empty")
        values[key] = value

    required = (
        "upstream_ip", "upstream_port", "sinkhole_ip", "proxy_ip",
        "ad_list_file", "sanction_list_file",
    )
    missing = [key for key in required if key not in values]
    if missing:
        raise ConfigError("Missing required key(s): " + ", ".join(missing))

    upstream_ip = _parse_ipv4("upstream_ip", values["upstream_ip"])
    upstream_port = _parse_int("upstream_port", values["upstream_port"], 1, 65535)
    sinkhole_ip = _parse_ipv4("sinkhole_ip", values["sinkhole_ip"])
    proxy_ip = _parse_ipv4("proxy_ip", values["proxy_ip"])

    try:
        timeout = float(values.get("upstream_timeout_sec", "2").strip())
    except ValueError as exc:
        raise ConfigError("Invalid value for upstream_timeout_sec: expected a positive number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigError("Invalid value for upstream_timeout_sec: expected a finite positive number")

    local_ttl = _parse_int("local_ttl", values.get("local_ttl", "60"), 1)
    cache_enabled = _parse_bool("cache_enabled", values.get("cache_enabled", "true"))
    real_dns_enabled = _parse_bool("real_dns_enabled", values.get("real_dns_enabled", "false"))

    cache_max_entries = None
    if "cache_max_entries" in values:
        cache_max_entries = _parse_int("cache_max_entries", values["cache_max_entries"], 1)

    if real_dns_enabled and (upstream_ip not in {"8.8.8.8", "1.1.1.1"} or upstream_port != 53):
        raise ConfigError("real_dns_enabled=true requires upstream_ip=8.8.8.8 or 1.1.1.1 and upstream_port=53")

    ad_list_file = Path(values["ad_list_file"])
    sanction_list_file = Path(values["sanction_list_file"])
    if not ad_list_file.is_absolute():
        ad_list_file = root / ad_list_file
    if not sanction_list_file.is_absolute():
        sanction_list_file = root / sanction_list_file

    for list_path in (ad_list_file, sanction_list_file):
        if not list_path.is_file():
            raise ConfigError(f"Required list file not found: {list_path.name}")

    return Config(
        base_dir=root,
        upstream_ip=upstream_ip,
        upstream_port=upstream_port,
        upstream_timeout_sec=timeout,
        sinkhole_ip=sinkhole_ip,
        proxy_ip=proxy_ip,
        local_ttl=local_ttl,
        ad_list_file=ad_list_file,
        sanction_list_file=sanction_list_file,
        cache_enabled=cache_enabled,
        cache_max_entries=cache_max_entries,
        real_dns_enabled=real_dns_enabled,
    )
