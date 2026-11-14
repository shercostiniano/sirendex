from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_partner_status_has_expected_contract() -> None:
    data = client.get("/api/partners").json()
    assert set(data) == {"tavily", "daytona", "nosana", "model", "fixture_safe"}


def test_search_is_demo_safe_without_key(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("APP_MODE", "fixture")
    response = client.get("/api/search", params={"q": "demo query"})
    assert response.status_code == 200
    assert response.json()["fixture"] is True
