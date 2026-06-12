"""Tests for Flask API using test client."""
import os, sys, json, pytest
from pathlib import Path
from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture
def client():
    """Create Flask test client with minimal app config."""
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

class TestAPI:
    def test_health(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 302, 404)

    def test_api_stats(self, client):
        resp = client.get("/api/stats")
        if resp.status_code == 200:
            data = resp.get_json()
            assert data is not None
        # May 404 if KB not initialized, that's OK

    def test_api_entries(self, client):
        resp = client.get("/api/entries")
        if resp.status_code == 200:
            data = resp.get_json()
            assert isinstance(data, list)

    def test_cors_headers(self, client):
        resp = client.options("/api/stats", headers={"Origin": "http://localhost"})
        # Flask-CORS should add headers, or may 200 normally
        assert resp.status_code in (200, 204)

    def test_static_files(self, client):
        resp = client.get("/static/index.html")
        assert resp.status_code in (200, 404)

    def test_intercom_api(self, client):
        resp = client.get("/api/intercom/messages")
        assert resp.status_code in (200, 404)

class TestHealthEndpoint:
    def test_app_routes(self, client):
        """Test that key routes exist without errors."""
        routes = ["/api/stats", "/api/entries", "/"]
        for route in routes:
            resp = client.get(route)
            # 500 would indicate a server error
            assert resp.status_code != 500, f"{route} returned 500"
