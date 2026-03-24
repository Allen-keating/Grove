# grove/integrations/github/async_client.py
"""Async wrapper around GitHubClient. Delegates blocking calls to a thread."""
import asyncio

from grove.integrations.github.client import GitHubClient


class AsyncGitHubClient:
    """Async facade for GitHubClient. Each method offloads to asyncio.to_thread."""

    def __init__(self, sync_client: GitHubClient):
        self._sync = sync_client

    async def create_issue(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.create_issue, *args, **kwargs)

    async def add_comment(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.add_comment, *args, **kwargs)

    async def get_pr_diff(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.get_pr_diff, *args, **kwargs)

    async def list_issues(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.list_issues, *args, **kwargs)

    async def write_file(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.write_file, *args, **kwargs)

    async def read_file(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.read_file, *args, **kwargs)

    async def read_directory_files(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.read_directory_files, *args, **kwargs)

    async def update_issue(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.update_issue, *args, **kwargs)

    async def create_milestone(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.create_milestone, *args, **kwargs)

    async def list_recent_commits(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.list_recent_commits, *args, **kwargs)

    async def list_open_prs(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.list_open_prs, *args, **kwargs)

    async def list_milestones(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.list_milestones, *args, **kwargs)

    async def get_repo_tree(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.get_repo_tree, *args, **kwargs)

    async def get_commit_detail(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.get_commit_detail, *args, **kwargs)

    async def list_recent_commits_detailed(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.list_recent_commits_detailed, *args, **kwargs)

    async def read_file_head(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.read_file_head, *args, **kwargs)

    async def get_pr_commits(self, *args, **kwargs):
        return await asyncio.to_thread(self._sync.get_pr_commits, *args, **kwargs)
