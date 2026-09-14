from marketing_measurement.config import Settings


def test_settings_use_safe_local_defaults(tmp_path):
    settings = Settings(data_dir=tmp_path)
    assert settings.random_seed == 20260910
    assert settings.data_dir == tmp_path
    assert "password" not in settings.model_dump_json().lower()


def test_settings_default_database_url():
    assert Settings().database_url == "duckdb:///data/local/marketing.duckdb"


def test_settings_use_mm_environment_prefix(monkeypatch):
    monkeypatch.setenv("MM_DATABASE_URL", "postgresql://localhost/marketing")
    assert Settings().database_url == "postgresql://localhost/marketing"


def test_settings_serialization_has_no_secret_like_field_names():
    serialized_fields = set(Settings().model_dump())
    assert not {"password", "secret", "token"} & serialized_fields
    assert all(
        term not in field.lower()
        for field in serialized_fields
        for term in ("password", "secret", "token")
    )
