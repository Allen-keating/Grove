# grove/integrations/github/client.py
"""GitHub API client using PyGithub + httpx."""
import logging
import httpx
from github import Github, GithubIntegration
from tenacity import retry, stop_after_attempt, wait_exponential
from grove.integrations.github.models import IssueData

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API wrapper. Authenticates as a GitHub App."""

    def __init__(self, app_id: str, private_key_path: str, installation_id: str):
        self.app_id = app_id
        self.private_key_path = private_key_path
        self.installation_id = installation_id
        self._github: Github | None = None
        self._token: str | None = None

    def _get_github(self) -> Github:
        if self._github is None:
            with open(self.private_key_path) as f:
                private_key = f.read()
            integration = GithubIntegration(
                integration_id=int(self.app_id),
                private_key=private_key,
            )
            access = integration.get_access_token(int(self.installation_id))
            self._token = access.token
            self._github = Github(self._token)
        return self._github

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def create_issue(self, repo, title, body="", labels=None, assignee=None) -> IssueData:
        gh = self._get_github()
        r = gh.get_repo(repo)
        issue = r.create_issue(title=title, body=body, labels=labels or [], assignee=assignee)
        logger.info("Created issue #%d in %s", issue.number, repo)
        return IssueData(
            number=issue.number, title=issue.title, body=issue.body or "",
            state=issue.state, labels=[label.name for label in issue.labels],
            assignees=[a.login for a in issue.assignees],
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def add_comment(self, repo, issue_number, body):
        gh = self._get_github()
        r = gh.get_repo(repo)
        issue = r.get_issue(issue_number)
        issue.create_comment(body)
        logger.info("Added comment to #%d in %s", issue_number, repo)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_pr_diff(self, repo, pr_number) -> str:
        gh = self._get_github()
        r = gh.get_repo(repo)
        pr = r.get_pull(pr_number)
        resp = httpx.get(
            pr.url,
            headers={"Authorization": f"token {self._token}", "Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_issues(self, repo, state="open", labels=None) -> list[IssueData]:
        gh = self._get_github()
        r = gh.get_repo(repo)
        label_objects = []
        if labels:
            for name in labels:
                try:
                    label_objects.append(r.get_label(name))
                except Exception:
                    logger.warning("Label '%s' not found in %s, skipping", name, repo)
        issues = r.get_issues(state=state, labels=label_objects or [])
        return [
            IssueData(number=i.number, title=i.title, body=i.body or "",
                      state=i.state, labels=[label.name for label in i.labels],
                      assignees=[a.login for a in i.assignees])
            for i in issues
        ]
