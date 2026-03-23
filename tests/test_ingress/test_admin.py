from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from grove.ingress.admin import create_admin_router
from grove.core.module_registry import ModuleRegistry
from grove.core.event_bus import EventBus, subscribe
from grove.core.events import EventType
from grove.core.storage import Storage
from pathlib import Path


class TestAdminAPI:
    @pytest.fixture
    def app(self, grove_dir: Path):
        bus = EventBus()
        storage = Storage(grove_dir)
        registry = ModuleRegistry(bus=bus, storage=storage)

        class DummyMod:
            @subscribe(EventType.PR_OPENED)
            async def handle(self, event): pass

        registry.add("pr_review", DummyMod(), enabled=True)
        registry.add("doc_sync", DummyMod(), enabled=False)

        app = FastAPI()
        app.include_router(create_admin_router(registry, admin_token="test_token"))
        return app

    def test_list_modules(self, app):
        client = TestClient(app)
        resp = client.get("/admin/modules", headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        modules = resp.json()["modules"]
        names = {m["name"] for m in modules}
        assert "pr_review" in names
        assert "doc_sync" in names

    def test_disable_module(self, app):
        client = TestClient(app)
        resp = client.post("/admin/modules/pr_review/disable",
                          headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_enable_module(self, app):
        client = TestClient(app)
        resp = client.post("/admin/modules/doc_sync/enable",
                          headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_unknown_module_404(self, app):
        client = TestClient(app)
        resp = client.post("/admin/modules/nonexistent/disable",
                          headers={"Authorization": "Bearer test_token"})
        assert resp.status_code == 404

    def test_no_auth_401(self, app):
        client = TestClient(app)
        resp = client.get("/admin/modules")
        assert resp.status_code == 401

    def test_wrong_token_401(self, app):
        client = TestClient(app)
        resp = client.get("/admin/modules", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401
