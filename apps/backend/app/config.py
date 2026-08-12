from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = REPOSITORY_ROOT / ".env"


class AppMode(StrEnum):
    MOCK = "mock"


class PlatformAccessProfile(StrEnum):
    LOOPBACK = "loopback"
    HTTPS = "https"


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlatformCookieSettings:
    name: str
    domain: None = None
    httponly: bool = True
    samesite: str = "strict"
    path: str = "/"
    secure: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    app_mode: AppMode = AppMode.MOCK
    control_enabled: bool = False
    database_url: str | None = None
    platform_ui_origin: str = "http://127.0.0.1:5173"
    platform_session_ttl_seconds: int = 28_800
    platform_access_profile: PlatformAccessProfile = PlatformAccessProfile.LOOPBACK
    platform_cookie: PlatformCookieSettings = PlatformCookieSettings(
        name="supersonic_platform_session_dev"
    )


def parse_app_mode(raw_mode: str | None) -> AppMode:
    if raw_mode is None:
        return AppMode.MOCK
    value = raw_mode.strip()
    if value in {"local", "api"}:
        raise ConfigurationError(
            f"APP_MODE={value!r} is reserved and not implemented; supported mode: mock"
        )
    if value != AppMode.MOCK:
        raise ConfigurationError(f"Invalid APP_MODE={value!r}; supported mode: mock")
    return AppMode.MOCK


def parse_bool_flag(raw_value: str | None, *, name: str) -> bool:
    if raw_value is None:
        return False
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ConfigurationError(f"{name}={raw_value!r} is not a valid boolean flag")


def normalize_optional_value(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def parse_platform_access_profile(raw_value: str | None) -> PlatformAccessProfile:
    value = "loopback" if raw_value is None else raw_value.strip().lower()
    try:
        return PlatformAccessProfile(value)
    except ValueError as error:
        raise ConfigurationError("PLATFORM_ACCESS_PROFILE must be loopback or https") from error


def parse_platform_session_ttl_seconds(raw_value: str | None) -> int:
    if raw_value is None:
        return 28_800
    try:
        value = int(raw_value.strip())
    except ValueError as error:
        raise ConfigurationError(
            "PLATFORM_SESSION_TTL_SECONDS must be a positive integer"
        ) from error
    if value < 1:
        raise ConfigurationError("PLATFORM_SESSION_TTL_SECONDS must be a positive integer")
    return value


def parse_platform_ui_origin(
    raw_value: str | None,
    *,
    profile: PlatformAccessProfile,
) -> str:
    value = "http://127.0.0.1:5173" if raw_value is None else raw_value.strip()
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        parsed_port = parts.port
    except ValueError:
        raise ConfigurationError("PLATFORM_UI_ORIGIN must be a concrete origin") from None
    if (
        not value
        or not parts.scheme
        or not parts.netloc
        or hostname is None
        or parsed_port is None and ":" in parts.netloc.rsplit("]", maxsplit=1)[-1]
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        raise ConfigurationError("PLATFORM_UI_ORIGIN must be a concrete origin")
    if profile is PlatformAccessProfile.LOOPBACK:
        if parts.scheme != "http" or hostname != "127.0.0.1":
            raise ConfigurationError("Loopback profile requires an HTTP 127.0.0.1 origin")
    elif parts.scheme != "https":
        raise ConfigurationError("HTTPS profile requires an HTTPS origin")
    return value.rstrip("/")


def platform_cookie_settings(profile: PlatformAccessProfile) -> PlatformCookieSettings:
    if profile is PlatformAccessProfile.HTTPS:
        return PlatformCookieSettings(
            name="__Host-supersonic_platform_session",
            secure=True,
        )
    return PlatformCookieSettings(name="supersonic_platform_session_dev")


def load_settings(
    *,
    env_file: Path = ROOT_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> RuntimeSettings:
    source = os.environ if environ is None else environ
    file_values = dotenv_values(env_file, interpolate=False) if env_file.is_file() else {}
    raw_mode = source.get("APP_MODE")
    if raw_mode is None:
        raw_mode = file_values.get("APP_MODE")
    raw_control = source.get("CONTROL_ENABLED")
    if raw_control is None:
        raw_control = file_values.get("CONTROL_ENABLED")
    raw_database_url = source.get("DATABASE_URL")
    if raw_database_url is None:
        raw_database_url = file_values.get("DATABASE_URL")
    raw_platform_ui_origin = source.get("PLATFORM_UI_ORIGIN")
    if raw_platform_ui_origin is None:
        raw_platform_ui_origin = file_values.get("PLATFORM_UI_ORIGIN")
    raw_platform_session_ttl = source.get("PLATFORM_SESSION_TTL_SECONDS")
    if raw_platform_session_ttl is None:
        raw_platform_session_ttl = file_values.get("PLATFORM_SESSION_TTL_SECONDS")
    raw_platform_access_profile = source.get("PLATFORM_ACCESS_PROFILE")
    if raw_platform_access_profile is None:
        raw_platform_access_profile = file_values.get("PLATFORM_ACCESS_PROFILE")
    platform_access_profile = parse_platform_access_profile(raw_platform_access_profile)
    return RuntimeSettings(
        app_mode=parse_app_mode(raw_mode),
        control_enabled=parse_bool_flag(raw_control, name="CONTROL_ENABLED"),
        database_url=normalize_optional_value(raw_database_url),
        platform_ui_origin=parse_platform_ui_origin(
            raw_platform_ui_origin,
            profile=platform_access_profile,
        ),
        platform_session_ttl_seconds=parse_platform_session_ttl_seconds(raw_platform_session_ttl),
        platform_access_profile=platform_access_profile,
        platform_cookie=platform_cookie_settings(platform_access_profile),
    )
