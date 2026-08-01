from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotenv import dotenv_values

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = REPOSITORY_ROOT / ".env"


class AppMode(StrEnum):
    MOCK = "mock"


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    app_mode: AppMode = AppMode.MOCK
    control_enabled: bool = False


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
    return RuntimeSettings(
        app_mode=parse_app_mode(raw_mode),
        control_enabled=parse_bool_flag(raw_control, name="CONTROL_ENABLED"),
    )
