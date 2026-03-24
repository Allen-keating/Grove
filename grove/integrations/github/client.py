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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def write_file(self, repo: str, path: str, content: str, message: str) -> None:
        """Create or update a file in the repo."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        try:
            existing = r.get_contents(path)
            r.update_file(path, message, content, existing.sha)
            logger.info("Updated file %s in %s", path, repo)
        except Exception:
            r.create_file(path, message, content)
            logger.info("Created file %s in %s", path, repo)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def read_file(self, repo: str, path: str) -> str:
        """Read a file from the repo."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        content = r.get_contents(path)
        return content.decoded_content.decode("utf-8")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def read_directory_files(self, repo: str, path: str, suffix: str = ".md") -> dict[str, str]:
        """Read all files in a repo directory. Returns {filename: content}."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        try:
            contents = r.get_contents(path)
        except Exception:
            return {}
        if not isinstance(contents, list):
            contents = [contents]
        return {
            item.name: item.decoded_content.decode("utf-8")
            for item in contents
            if item.type == "file" and item.name.endswith(suffix)
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def update_issue(self, repo: str, issue_number: int, **kwargs) -> None:
        """Update an issue. Accepts: title, body, state, labels, assignee, milestone."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        issue = r.get_issue(issue_number)
        issue.edit(**kwargs)
        logger.info("Updated issue #%d in %s", issue_number, repo)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def create_milestone(self, repo: str, title: str, due_on: str | None = None):
        """Create a milestone. Returns the milestone number."""
        from datetime import datetime
        gh = self._get_github()
        r = gh.get_repo(repo)
        kwargs = {"title": title}
        if due_on:
            kwargs["due_on"] = datetime.fromisoformat(due_on)
        milestone = r.create_milestone(**kwargs)
        logger.info("Created milestone '%s' (#%d) in %s", title, milestone.number, repo)
        return milestone.number

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_recent_commits(self, repo: str, since: str, author: str | None = None) -> list:
        """List commits since a datetime string. Returns list of dicts."""
        from datetime import datetime
        gh = self._get_github()
        r = gh.get_repo(repo)
        kwargs = {"since": datetime.fromisoformat(since)}
        if author:
            kwargs["author"] = author
        commits = r.get_commits(**kwargs)
        return [
            {"sha": c.sha[:7], "message": c.commit.message.split("\n")[0],
             "author": c.commit.author.name, "date": c.commit.author.date.isoformat()}
            for c in commits[:50]
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_open_prs(self, repo: str) -> list:
        gh = self._get_github()
        r = gh.get_repo(repo)
        prs = r.get_pulls(state="open")
        return [
            {"number": pr.number, "title": pr.title, "author": pr.user.login,
             "created_at": pr.created_at.isoformat(), "updated_at": pr.updated_at.isoformat(),
             "review_requested": bool(list(pr.get_review_requests()[0]))}
            for pr in prs[:20]
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_milestones(self, repo: str) -> list:
        gh = self._get_github()
        r = gh.get_repo(repo)
        milestones = r.get_milestones(state="open")
        return [
            {"number": m.number, "title": m.title,
             "due_on": m.due_on.isoformat() if m.due_on else None,
             "open_issues": m.open_issues, "closed_issues": m.closed_issues}
            for m in milestones
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_repo_tree(self, repo: str, recursive: bool = True) -> list[dict]:
        """Get the full repository file tree via Git Trees API."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        default_branch = r.default_branch
        tree = r.get_git_tree(default_branch, recursive=recursive)
        IGNORE_PREFIXES = (
            "node_modules/", ".git/", "__pycache__/", "vendor/",
            ".venv/", "venv/", "dist/", "build/", ".tox/",
        )
        return [
            {"path": item.path, "type": item.type, "size": item.size or 0}
            for item in tree.tree
            if not any(item.path.startswith(p) or f"/{p}" in item.path for p in IGNORE_PREFIXES)
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_commit_detail(self, repo: str, sha: str) -> dict:
        """Get detailed commit info including per-file changes."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        commit = r.get_commit(sha)
        return {
            "sha": commit.sha[:7],
            "message": commit.commit.message.split("\n")[0],
            "author": commit.commit.author.name,
            "date": commit.commit.author.date.isoformat(),
            "files": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in (commit.files or [])
            ],
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def list_recent_commits_detailed(
        self, repo: str, since: str, until: str | None = None, max_commits: int = 200,
    ) -> list[dict]:
        """List recent commits with per-file change details. Caps at max_commits."""
        from datetime import datetime
        gh = self._get_github()
        r = gh.get_repo(repo)
        kwargs = {"since": datetime.fromisoformat(since)}
        if until:
            kwargs["until"] = datetime.fromisoformat(until)
        commits = r.get_commits(**kwargs)
        results = []
        for c in commits[:max_commits]:
            detail = self.get_commit_detail(repo, c.sha)
            results.append(detail)
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def read_file_head(self, repo: str, path: str, max_lines: int = 100) -> str:
        """Read the first N lines of a file. Downloads full file, truncates locally."""
        content = self.read_file(repo, path)
        lines = content.split("\n")
        return "\n".join(lines[:max_lines])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4))
    def get_pr_commits(self, repo: str, pr_number: int) -> list[dict]:
        """Get all commits associated with a PR."""
        gh = self._get_github()
        r = gh.get_repo(repo)
        pr = r.get_pull(pr_number)
        return [
            {
                "sha": c.sha[:7],
                "message": c.commit.message.split("\n")[0],
                "author": c.commit.author.name,
            }
            for c in pr.get_commits()
        ]
