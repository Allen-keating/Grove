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


from unittest.mock import MagicMock

class TestGitHubClientNewMethods:
    def _make_client(self):
        return GitHubClient(app_id="1", private_key_path="/tmp/fake.pem", installation_id="2")

    def test_get_repo_tree(self):
        client = self._make_client()
        mock_tree = MagicMock()
        mock_element = MagicMock()
        mock_element.path = "grove/main.py"
        mock_element.type = "blob"
        mock_element.size = 1234
        mock_tree.tree = [mock_element]

        mock_repo = MagicMock()
        mock_repo.get_git_tree.return_value = mock_tree
        mock_repo.default_branch = "main"
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.get_repo_tree("org/repo")
        assert len(result) == 1
        assert result[0]["path"] == "grove/main.py"
        assert result[0]["type"] == "blob"
        assert result[0]["size"] == 1234
        mock_repo.get_git_tree.assert_called_once()

    def test_get_repo_tree_filters_ignored(self):
        client = self._make_client()
        mock_tree = MagicMock()
        items = []
        for path in ["grove/main.py", "node_modules/foo/bar.js", "__pycache__/cache.pyc", ".venv/bin/python"]:
            el = MagicMock()
            el.path = path
            el.type = "blob"
            el.size = 100
            items.append(el)
        mock_tree.tree = items
        mock_repo = MagicMock()
        mock_repo.get_git_tree.return_value = mock_tree
        mock_repo.default_branch = "main"
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.get_repo_tree("org/repo")
        assert len(result) == 1
        assert result[0]["path"] == "grove/main.py"

    def test_get_commit_detail(self):
        client = self._make_client()
        mock_file = MagicMock()
        mock_file.filename = "main.py"
        mock_file.status = "modified"
        mock_file.additions = 10
        mock_file.deletions = 3
        mock_commit = MagicMock()
        mock_commit.sha = "abc1234567"
        mock_commit.commit.message = "feat: add feature"
        mock_commit.commit.author.name = "alice"
        mock_commit.commit.author.date.isoformat.return_value = "2026-03-23T10:00:00"
        mock_commit.files = [mock_file]

        mock_repo = MagicMock()
        mock_repo.get_commit.return_value = mock_commit
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.get_commit_detail("org/repo", "abc1234567")
        assert result["sha"] == "abc1234"
        assert result["message"] == "feat: add feature"
        assert result["files"][0]["filename"] == "main.py"
        assert result["files"][0]["additions"] == 10

    def test_list_recent_commits_detailed_respects_max(self):
        client = self._make_client()
        mock_commits = []
        for i in range(5):
            mc = MagicMock()
            mc.sha = f"sha{i:07d}"
            mc.commit.message = f"commit {i}"
            mc.commit.author.name = "alice"
            mc.commit.author.date.isoformat.return_value = f"2026-03-23T{i:02d}:00:00"
            mc.files = []
            mock_commits.append(mc)

        mock_repo = MagicMock()
        mock_repo.get_commits.return_value = mock_commits
        mock_repo.get_commit.side_effect = lambda sha: next(c for c in mock_commits if c.sha == sha)
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        client._github = mock_gh

        result = client.list_recent_commits_detailed("org/repo", since="2026-03-22T00:00:00", max_commits=3)
        assert len(result) == 3
