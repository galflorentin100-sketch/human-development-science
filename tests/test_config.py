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
