"""Configuration resolution and its handling of bad input."""

import pytest

from src.config import build_settings, get_settings, load_config, reset_settings


def test_defaults_are_safe_without_any_environment():
    settings = build_settings()
    assert settings.dry_run is True
    assert settings.missing_credentials() == ["openai", "elevenlabs", "twilio", "gmail"]


def test_env_overrides_are_applied(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("RETRY_ATTEMPTS", "7")
    monkeypatch.setenv("HTTP_TIMEOUT", "12")
    settings = build_settings()
    assert settings.dry_run is False
    assert settings.retry_attempts == 7
    assert settings.http_timeout == 12


@pytest.mark.parametrize("value", ["ture", "maybe", "  "])
def test_unparseable_boolean_keeps_the_safe_default(monkeypatch, value):
    """A typo in DRY_RUN must never arm live calls."""
    monkeypatch.setenv("DRY_RUN", value)
    assert build_settings().dry_run is True


def test_unparseable_int_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("CALL_MAX_WAIT", "two minutes")
    assert build_settings().call_max_wait == 120


def test_out_of_range_values_are_clamped(monkeypatch):
    monkeypatch.setenv("RETRY_ATTEMPTS", "0")
    monkeypatch.setenv("CALL_POLL_INTERVAL", "-5")
    monkeypatch.setenv("RETRY_BACKOFF", "0.2")
    settings = build_settings()
    assert settings.retry_attempts == 1
    assert settings.call_poll_interval == 1
    # A backoff below 1.0 would shrink instead of grow the delay.
    assert settings.retry_backoff == 1.0


def test_retry_backoff_is_configurable(monkeypatch):
    monkeypatch.setenv("RETRY_BACKOFF", "2.5")
    assert build_settings().retry_backoff == 2.5


def test_malformed_yaml_is_reported_and_ignored(tmp_path, caplog):
    path = tmp_path / "broken.yaml"
    path.write_text("agents: [unclosed\n", encoding="utf-8")
    with caplog.at_level("ERROR"):
        assert load_config(str(path)) == {}
    assert "not valid YAML" in caplog.text


def test_non_mapping_yaml_is_rejected(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    assert load_config(str(path)) == {}


def test_empty_yaml_is_an_empty_mapping(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_config(str(path)) == {}


def test_missing_config_file_falls_back_to_defaults(tmp_path):
    settings = build_settings(str(tmp_path / "does-not-exist.yaml"))
    assert settings.raw_config == {}
    assert settings.log_level == "INFO"


def test_non_numeric_config_values_do_not_crash_startup(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("calls:\n  poll_interval: fast\n  max_wait_seconds: soon\n", encoding="utf-8")
    settings = build_settings(str(path))
    assert settings.call_poll_interval == 5
    assert settings.call_max_wait == 120


def test_section_tolerates_missing_and_scalar_nodes(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("integrations: not-a-mapping\n", encoding="utf-8")
    settings = build_settings(str(path))
    assert settings.section("integrations", "gmail") == {}
    assert settings.section("nope") == {}


def test_get_settings_caches_until_refreshed(monkeypatch):
    first = get_settings()
    assert get_settings() is first
    monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-test")
    assert get_settings().openai_model == first.openai_model
    assert get_settings(refresh=True).openai_model == "gpt-test"
    reset_settings()


def test_relative_credential_paths_resolve_against_the_project_root(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "creds/google.json")
    settings = build_settings()
    assert settings.google_credentials_path.endswith("google.json")
    assert str(settings.project_root) in settings.google_credentials_path
