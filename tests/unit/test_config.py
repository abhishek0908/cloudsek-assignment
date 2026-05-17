from app.core.config import Settings


class TestSettings:

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URL", "mongodb://test:27017")
        monkeypatch.setenv("DATABASE_NAME", "test_db")
        monkeypatch.setenv("APP_NAME", "test-app")
        monkeypatch.setenv("APP_VERSION", "0.0.0")
        monkeypatch.setenv("ENVIRONMENT", "testing")
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        monkeypatch.setenv("REQUEST_TIMEOUT", "10")

        settings = Settings()

        assert settings.mongodb_url == "mongodb://test:27017"
        assert settings.database_name == "test_db"
        assert settings.app_name == "test-app"
        assert settings.app_version == "0.0.0"
        assert settings.environment == "testing"
        assert settings.log_level == "INFO"
        assert settings.request_timeout == 10
