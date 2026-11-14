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


def test_incident_feed_contract(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "fixture")
    response = client.get("/api/incidents", params={"area": "Shibuya, Tokyo", "days": 7})
    assert response.status_code == 200
    data = response.json()
    assert data["area"] == "Shibuya, Tokyo"
    assert data["activity"]["score"] <= 100
    assert data["incidents"]
    assert {"id", "category", "title", "source_url", "lat", "lng"} <= set(data["incidents"][0])
    assert data["partners"]["tavily"]["status"] == "fixture"
    assert data["partners"]["daytona"]["status"] == "skipped"
    assert "not a prediction" in data["disclaimer"].lower()


def test_sirendex_map_ui_is_served() -> None:
    html = client.get("/").text
    assert "SIRENDEX" in html
    assert "MURDERDEX" not in html
    assert '<div class="brandmark">🚨</div>' in html
    assert "<small>LIVE INCIDENT MAP</small>" in html
    assert "<small>SPIDERDEX LIVE INCIDENT MAP</small>" not in html
    assert 'id="map"' in html
    assert "Incident Activity Index" in html
    assert "ASSAULT" in html


def test_ui_uses_mapbox_gl_not_leaflet_or_carto() -> None:
    html = client.get("/").text
    assert "mapbox-gl.js" in html
    assert "new mapboxgl.Map" in html
    assert "mapbox://styles/mapbox/dark-v11" in html
    assert "leaflet" not in html.lower()
    assert "cartocdn.com" not in html


def test_reverse_geocode_contract(monkeypatch) -> None:
    monkeypatch.setattr("app.main._reverse_area", lambda lat, lng: "Shibuya, Tokyo")
    response = client.get("/api/reverse-geocode", params={"lat": 35.66, "lng": 139.70})
    assert response.status_code == 200
    assert response.json() == {"area": "Shibuya, Tokyo"}


def test_public_map_config_exposes_only_public_mapbox_token(monkeypatch) -> None:
    monkeypatch.setenv("MAPBOX_ACCESS_TOKEN", "pk.test-public-token")
    assert client.get("/api/config").json() == {"mapbox_access_token": "pk.test-public-token"}


def test_ui_uses_mapbox_not_carto() -> None:
    html = client.get("/").text
    assert "api.mapbox.com" in html
    assert "cartocdn.com" not in html
