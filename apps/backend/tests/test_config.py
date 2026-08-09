from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import ROOT_ENV_FILE, AppMode, ConfigurationError, load_settings
from app.main import create_app


def test_missing_root_env_uses_mock_default(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / ".env", environ={})

    assert ROOT_ENV_FILE == Path(__file__).resolve().parents[3] / ".env"
    assert settings.app_mode is AppMode.MOCK


def test_database_url_is_optional(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / ".env", environ={})

    assert settings.database_url is None


def test_process_database_url_overrides_root_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://file_user:file_pass@db/file_db\n",
        encoding="utf-8",
    )

    settings = load_settings(
        env_file=env_file,
        environ={
            "DATABASE_URL": "postgresql+psycopg://process_user:process_pass@db/process_db"
        },
    )

    assert settings.database_url == (
        "postgresql+psycopg://process_user:process_pass@db/process_db"
    )


def test_blank_database_url_is_treated_as_unconfigured(tmp_path: Path) -> None:
    settings = load_settings(
        env_file=tmp_path / ".env",
        environ={"DATABASE_URL": "   "},
    )

    assert settings.database_url is None


def test_blank_process_database_url_still_overrides_root_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://file_user:file_pass@db/file_db\n",
        encoding="utf-8",
    )

    settings = load_settings(
        env_file=env_file,
        environ={"DATABASE_URL": "   "},
    )

    assert settings.database_url is None


def test_root_env_rejects_reserved_mode(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_MODE=api\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"reserved.*mock"):
        load_settings(env_file=env_file, environ={})


def test_process_environment_overrides_root_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_MODE=api\n", encoding="utf-8")

    settings = load_settings(env_file=env_file, environ={"APP_MODE": "mock"})

    assert settings.app_mode is AppMode.MOCK


@pytest.mark.parametrize("mode", ["local", "api", "production", ""])
def test_unsupported_or_invalid_modes_fail_clearly(tmp_path: Path, mode: str) -> None:
    with pytest.raises(ConfigurationError, match=r"supported mode: mock"):
        load_settings(env_file=tmp_path / ".env", environ={"APP_MODE": mode})


async def test_health_uses_validated_mode_without_exposing_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        (
            "APP_MODE=mock\n"
            "LLM_API_KEY=do-not-return-this\n"
            "DATABASE_URL=postgresql+psycopg://file_user:file_pass@db/file_db\n"
        ),
        encoding="utf-8",
    )
    settings = load_settings(env_file=env_file, environ={})
    api = create_app(settings=settings)

    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "mock"}

def test_control_flag_defaults_to_disabled(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / ".env", environ={})

    assert settings.control_enabled is False


def test_control_flag_reads_true_from_root_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CONTROL_ENABLED=true\n", encoding="utf-8")

    settings = load_settings(env_file=env_file, environ={})

    assert settings.control_enabled is True


def test_control_flag_process_value_overrides_root_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CONTROL_ENABLED=true\n", encoding="utf-8")

    settings = load_settings(env_file=env_file, environ={"CONTROL_ENABLED": "false"})

    assert settings.control_enabled is False


@pytest.mark.parametrize("raw", ["maybe", "2", "TRUE-ish"])
def test_control_flag_rejects_invalid_values(tmp_path: Path, raw: str) -> None:
    with pytest.raises(ConfigurationError, match=r"CONTROL_ENABLED"):
        load_settings(env_file=tmp_path / ".env", environ={"CONTROL_ENABLED": raw})
