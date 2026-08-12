import ast
import hashlib
import inspect
import re

import pytest

from app.adapters.security import PwdlibPasswordHasher
from app.config import (
    ConfigurationError,
    PlatformAccessProfile,
    load_settings,
)
from app.platform.security import (
    CredentialStoreError,
    ExactOriginPolicy,
    PasswordHasher,
    digest_session_token,
    issue_session_token,
)
from app.platform.throttle import LoginThrottle


def test_platform_security_defaults_are_loopback_and_have_safe_cookie_settings(tmp_path) -> None:
    settings = load_settings(env_file=tmp_path / ".env", environ={})

    assert settings.platform_ui_origin == "http://127.0.0.1:5173"
    assert settings.platform_session_ttl_seconds == 28_800
    assert settings.platform_access_profile is PlatformAccessProfile.LOOPBACK
    assert settings.platform_cookie.name == "supersonic_platform_session_dev"
    assert settings.platform_cookie.domain is None
    assert settings.platform_cookie.httponly is True
    assert settings.platform_cookie.samesite == "strict"
    assert settings.platform_cookie.path == "/"
    assert settings.platform_cookie.secure is False


def test_https_profile_uses_host_cookie_and_exact_origin_policy(tmp_path) -> None:
    settings = load_settings(
        env_file=tmp_path / ".env",
        environ={
            "PLATFORM_UI_ORIGIN": "https://platform.example.test",
            "PLATFORM_ACCESS_PROFILE": "https",
        },
    )

    assert settings.platform_cookie.name == "__Host-supersonic_platform_session"
    assert settings.platform_cookie.secure is True
    assert ExactOriginPolicy(settings.platform_ui_origin).allows("https://platform.example.test")
    assert not ExactOriginPolicy(settings.platform_ui_origin).allows("https://platform.example.test/")
    assert not ExactOriginPolicy(settings.platform_ui_origin).allows("https://evil.example.test")
    assert not ExactOriginPolicy(settings.platform_ui_origin).allows(None)


def test_process_environment_overrides_platform_settings_from_env_file(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        (
            "PLATFORM_UI_ORIGIN=https://file.example.test\n"
            "PLATFORM_SESSION_TTL_SECONDS=120\n"
            "PLATFORM_ACCESS_PROFILE=https\n"
        ),
        encoding="utf-8",
    )

    settings = load_settings(
        env_file=env_file,
        environ={
            "PLATFORM_UI_ORIGIN": "http://127.0.0.1:4173",
            "PLATFORM_SESSION_TTL_SECONDS": "3600",
            "PLATFORM_ACCESS_PROFILE": "loopback",
        },
    )

    assert settings.platform_ui_origin == "http://127.0.0.1:4173"
    assert settings.platform_session_ttl_seconds == 3_600
    assert settings.platform_access_profile is PlatformAccessProfile.LOOPBACK


@pytest.mark.parametrize(
    "environ",
    [
        {"PLATFORM_UI_ORIGIN": "http://localhost:5173"},
        {"PLATFORM_UI_ORIGIN": "http://127.0.0.1:5173/path"},
        {"PLATFORM_UI_ORIGIN": "http://user@127.0.0.1:5173"},
        {"PLATFORM_UI_ORIGIN": "http://127.0.0.1:5173?next=1"},
        {"PLATFORM_UI_ORIGIN": "http://127.0.0.1:5173#section"},
        {"PLATFORM_UI_ORIGIN": "https://127.0.0.1:5173"},
        {
            "PLATFORM_UI_ORIGIN": "https://:443",
            "PLATFORM_ACCESS_PROFILE": "https",
        },
        {
            "PLATFORM_UI_ORIGIN": "https://platform.example.test:not-a-port",
            "PLATFORM_ACCESS_PROFILE": "https",
        },
        {
            "PLATFORM_UI_ORIGIN": "https://platform.example.test:99999",
            "PLATFORM_ACCESS_PROFILE": "https",
        },
        {
            "PLATFORM_UI_ORIGIN": "http://127.0.0.1:5173",
            "PLATFORM_ACCESS_PROFILE": "https",
        },
        {"PLATFORM_ACCESS_PROFILE": "lan"},
        {"PLATFORM_SESSION_TTL_SECONDS": "0"},
        {"PLATFORM_SESSION_TTL_SECONDS": "not-a-number"},
    ],
)
def test_invalid_platform_configuration_fails_without_echoing_origin(
    tmp_path,
    environ: dict[str, str],
) -> None:
    with pytest.raises(ConfigurationError) as captured:
        load_settings(env_file=tmp_path / ".env", environ=environ)

    assert "@" not in str(captured.value)
    assert "next=1" not in str(captured.value)


def test_session_token_digest_is_sha256_hex_and_does_not_retain_raw_secret() -> None:
    token = issue_session_token()
    digest = digest_session_token(token)

    assert len(token) >= 43
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in digest


def test_platform_password_port_is_framework_free_and_has_typed_verification_result() -> None:
    source = inspect.getsource(__import__("app.platform.security", fromlist=["unused"]))
    imported_roots = {
        node.module.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert PasswordHasher._is_protocol is True
    assert {"hash", "verify_and_update", "dummy_verify"} <= set(PasswordHasher.__dict__)
    assert imported_roots.isdisjoint({"fastapi", "sqlalchemy", "pwdlib"})


def test_pwdlib_adapter_verifies_hashes_and_rehashes_without_disclosing_secrets() -> None:
    adapter = PwdlibPasswordHasher()
    password = "correct horse battery staple"
    stored_hash = adapter.hash(password)

    verified = adapter.verify_and_update(password, stored_hash)
    rejected = adapter.verify_and_update("wrong password", stored_hash)
    adapter.dummy_verify("unknown-user-password")

    assert verified.verified is True
    assert verified.updated_hash is None or verified.updated_hash != stored_hash
    assert rejected.verified is False
    assert rejected.updated_hash is None
    assert password not in stored_hash
    assert password not in repr(verified)


def test_pwdlib_adapter_maps_unrecognized_hash_to_safe_credential_store_error() -> None:
    raw_password = "password-must-not-leak"
    malformed_hash = "not-a-recognized-hash-secret"

    with pytest.raises(CredentialStoreError) as captured:
        PwdlibPasswordHasher().verify_and_update(raw_password, malformed_hash)

    assert str(captured.value) == "Credential store contains an invalid password hash."
    assert raw_password not in str(captured.value)
    assert malformed_hash not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


def test_login_throttle_normalizes_keys_locks_and_reports_ceil_retry_after() -> None:
    now = [100.0]
    throttle = LoginThrottle(clock=lambda: now[0])

    for _ in range(5):
        throttle.record_failure("  ALICE  ", "client-a")

    blocked = throttle.check("alice", "client-a")
    now[0] += 0.2

    assert blocked.allowed is False
    assert blocked.retry_after == 30
    assert throttle.check("alice", "client-b").allowed is True
    assert throttle.check("bob", "client-a").allowed is True
    assert throttle.check("alice", "client-a").retry_after == 30


def test_login_throttle_allows_login_when_lockout_expires() -> None:
    now = [100.0]
    throttle = LoginThrottle(clock=lambda: now[0])

    for _ in range(5):
        throttle.record_failure("alice", "client-a")

    now[0] = 129.999
    assert throttle.check("alice", "client-a").allowed is False

    now[0] = 130.0
    assert throttle.check("alice", "client-a").allowed is True
    assert throttle.entry_count == 0


def test_login_throttle_expires_failures_resets_and_evicts_lru_entries() -> None:
    now = [0.0]
    throttle = LoginThrottle(clock=lambda: now[0], max_entries=2)

    throttle.record_failure("Alice", "client-a")
    throttle.record_failure("Bob", "client-b")
    throttle.check("Alice", "client-a")
    throttle.record_failure("Carol", "client-c")

    assert throttle.entry_count == 2
    assert throttle.check("Bob", "client-b").allowed is True

    now[0] += 61
    throttle.record_failure("alice", "client-a")
    throttle.record_failure("bob", "client-b")
    throttle.record_success("bob", "client-b")

    assert throttle.entry_count == 1
    assert throttle.check("alice", "client-a").allowed is True
    assert throttle.check("bob", "client-b").allowed is True
