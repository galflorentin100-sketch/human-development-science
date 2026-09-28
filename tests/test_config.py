import pytest
from app.config import Settings


def test_invalid_environment_fails_closed():
    with pytest.raises(ValueError):
        Settings(environment="prod")


def test_production_requires_database_url():
    with pytest.raises(ValueError):
        Settings(environment="production")


def test_development_defaults_are_valid():
    settings=Settings()
    assert settings.environment=="development"


def test_production_requires_identity_secret():
    with pytest.raises(ValueError, match="HDS_AUTH_HMAC_SECRET"):
        Settings(environment="production", database_url="postgresql://example", auth_hmac_secret=None)


def test_production_accepts_identity_secret():
    settings=Settings(
        environment="production",
        database_url="postgresql://example",
        auth_hmac_secret="secret",
        owner_external_subject="owner-subject",
        code_runner_mode="isolated",
    )
    assert settings.auth_hmac_secret=="secret"


def test_production_rejects_non_isolated_code_runner():
    with pytest.raises(ValueError, match="HDS_CODE_RUNNER_MODE=isolated"):
        Settings(
            environment="production",
            database_url="postgresql://example",
            auth_hmac_secret="secret",
            owner_external_subject="owner-subject",
        )
