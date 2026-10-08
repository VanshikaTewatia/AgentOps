from app.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.APP_NAME == "AGENTOPS"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.EMBEDDING_DIMENSION == 1536
    assert isinstance(settings.ALLOWED_CORS_ORIGINS, list)
    assert len(settings.ALLOWED_CORS_ORIGINS) > 0


def test_cors_origins_parsing():
    settings = Settings(ALLOWED_CORS_ORIGINS="http://localhost:3000,http://example.com")
    assert "http://localhost:3000" in settings.ALLOWED_CORS_ORIGINS
    assert "http://example.com" in settings.ALLOWED_CORS_ORIGINS
