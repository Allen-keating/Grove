import hashlib
import hmac
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from grove.core.events import EventType
from grove.ingress.github_webhook import create_github_webhook_router


class TestGitHubWebhook:
    def _sign(self, payload: bytes, secret: str) -> str:
        mac = hmac.new(secret.encode(), payload, hashlib.sha256)
        return f"sha256={mac.hexdigest()}"

    def _make_app(self):
        app = FastAPI()
        received_events = []

        async def on_event(event):
            received_events.append(event)

        router = create_github_webhook_router(webhook_secret="test_secret", on_event=on_event)
        app.include_router(router)
        return app, received_events

    def test_valid_signature_accepted(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = json.dumps({
            "action": "opened",
            "issue": {"number": 1, "title": "Test", "body": "", "state": "open",
                       "labels": [], "assignees": [], "user": {"login": "zhangsan"}},
        }).encode()
        sig = self._sign(payload, "test_secret")
        resp = client.post("/webhook/github", content=payload,
            headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "issues", "Content-Type": "application/json"})
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = b'{"action":"opened"}'
        resp = client.post("/webhook/github", content=payload,
            headers={"X-Hub-Signature-256": "sha256=invalid", "X-GitHub-Event": "issues", "Content-Type": "application/json"})
        assert resp.status_code == 403

    def test_issue_opened_produces_event(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = json.dumps({
            "action": "opened",
            "issue": {"number": 42, "title": "Bug report", "body": "desc", "state": "open",
                       "labels": [{"name": "bug"}], "assignees": [{"login": "zhangsan"}],
                       "user": {"login": "zhangsan"}},
        }).encode()
        sig = self._sign(payload, "test_secret")
        client.post("/webhook/github", content=payload,
            headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "issues", "Content-Type": "application/json"})
        assert len(events) == 1
        assert events[0].type == EventType.ISSUE_OPENED
        assert events[0].source == "github"
        assert events[0].payload["issue"]["number"] == 42

    def test_pr_opened_produces_event(self):
        app, events = self._make_app()
        client = TestClient(app)
        payload = json.dumps({
            "action": "opened",
            "pull_request": {"number": 10, "title": "Fix", "body": "", "state": "open",
                              "user": {"login": "lisi"}},
        }).encode()
        sig = self._sign(payload, "test_secret")
        client.post("/webhook/github", content=payload,
            headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "pull_request", "Content-Type": "application/json"})
        assert len(events) == 1
        assert events[0].type == EventType.PR_OPENED
