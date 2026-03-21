from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from grove.ingress.health import create_health_router, HealthState


class TestHealth:
    def test_health_endpoint_healthy(self):
        app = FastAPI()
        state = HealthState()
        state.lark_ws_connected = True
        state.scheduler_running = True
        state.last_event_processed = datetime.now(timezone.utc)
        app.include_router(create_health_router(state))
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["fastapi"] is True
        assert data["lark_ws_connected"] is True
        assert data["scheduler_running"] is True

    def test_health_endpoint_degraded(self):
        app = FastAPI()
        state = HealthState()
        state.lark_ws_connected = False
        state.scheduler_running = True
        app.include_router(create_health_router(state))
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["lark_ws_connected"] is False
