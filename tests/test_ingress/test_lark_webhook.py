# tests/test_ingress/test_lark_webhook.py
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from grove.ingress.lark_webhook import create_lark_webhook_router


@pytest.fixture
def app_with_token():
    on_event = AsyncMock()
    app = FastAPI()
    app.include_router(create_lark_webhook_router(
        on_event=on_event, verification_token="secret_token",
    ))
    return app, on_event


@pytest.fixture
def app_without_token():
    on_event = AsyncMock()
    app = FastAPI()
    app.include_router(create_lark_webhook_router(on_event=on_event))
    return app, on_event


class TestLarkWebhookVerification:
    def test_challenge_bypasses_verification(self, app_with_token):
        app, _ = app_with_token
        client = TestClient(app)
        resp = client.post("/webhook/lark", json={"challenge": "test123"})
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "test123"}

    def test_valid_token_accepted(self, app_with_token):
        app, on_event = app_with_token
        client = TestClient(app)
        resp = client.post("/webhook/lark", json={
            "header": {"event_type": "drive.file.edit_v1", "token": "secret_token"},
        })
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        on_event.assert_called_once()

    def test_invalid_token_rejected(self, app_with_token):
        app, on_event = app_with_token
        client = TestClient(app)
        resp = client.post("/webhook/lark", json={
            "header": {"event_type": "drive.file.edit_v1", "token": "wrong_token"},
        })
        assert resp.status_code == 403
        on_event.assert_not_called()

    def test_missing_token_rejected(self, app_with_token):
        app, on_event = app_with_token
        client = TestClient(app)
        resp = client.post("/webhook/lark", json={
            "header": {"event_type": "drive.file.edit_v1"},
        })
        assert resp.status_code == 403
        on_event.assert_not_called()

    def test_no_verification_configured(self, app_without_token):
        app, on_event = app_without_token
        client = TestClient(app)
        resp = client.post("/webhook/lark", json={
            "header": {"event_type": "drive.file.edit_v1"},
        })
        assert resp.status_code == 200
        on_event.assert_called_once()
