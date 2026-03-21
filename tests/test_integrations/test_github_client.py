# tests/test_integrations/test_github_client.py
from grove.integrations.github.client import GitHubClient
from grove.integrations.github.models import IssueData


class TestGitHubClient:
    def test_client_init(self):
        client = GitHubClient(
            app_id="123",
            private_key_path="/tmp/fake.pem",
            installation_id="456",
        )
        assert client.app_id == "123"

    def test_issue_data_model(self):
        issue = IssueData(
            number=42,
            title="Test issue",
            body="Description",
            state="open",
            labels=["bug"],
            assignees=["zhangsan"],
        )
        assert issue.number == 42
        assert issue.title == "Test issue"
        assert "bug" in issue.labels
