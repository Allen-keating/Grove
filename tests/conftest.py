# tests/conftest.py
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def grove_dir(tmp_path: Path) -> Path:
    """Create a temporary .grove/ directory with example config files."""
    grove = tmp_path / ".grove"
    grove.mkdir()
    (grove / "logs").mkdir()
    (grove / "memory").mkdir()
    (grove / "memory" / "profiles").mkdir()
    (grove / "memory" / "snapshots").mkdir()
    (grove / "memory" / "decisions").mkdir()
    (grove / "memory" / "conversations").mkdir()
    (grove / "docs-sync").mkdir()
    return grove


@pytest.fixture
def sample_team_yml(grove_dir: Path) -> Path:
    """Write a sample team.yml for testing."""
    team_file = grove_dir / "team.yml"
    team_file.write_text(
        """\
version: 1

team:
  - github: zhangsan
    lark_id: "ou_xxxxxxxx1"
    name: 张三
    role: frontend
    skills: [react, typescript, css]
    authority: member
  - github: lisi
    lark_id: "ou_xxxxxxxx2"
    name: 李四
    role: backend
    skills: [python, fastapi, postgresql]
    authority: lead
  - github: wangwu
    lark_id: "ou_xxxxxxxx3"
    name: 王五
    role: fullstack
    skills: [react, node, docker]
    authority: member
""",
        encoding="utf-8",
    )
    return team_file


@pytest.fixture
def sample_config_yml(grove_dir: Path) -> Path:
    """Write a sample config.yml for testing."""
    config_file = grove_dir / "config.yml"
    config_file.write_text(
        """\
version: 1

project:
  name: "Test Project"
  repo: "testorg/testrepo"
  language: "zh-CN"

lark:
  app_id: "test_app_id"
  app_secret: "test_app_secret"
  chat_id: "oc_test"
  space_id: "spc_test"

github:
  app_id: "12345"
  private_key_path: "/tmp/test-key.pem"
  installation_id: "67890"
  webhook_secret: "test_webhook_secret"

llm:
  api_key: "test_api_key"
  model: "claude-sonnet-4-6"

persona:
  name: "Grove"
  tone: "专业但不刻板"
  reminder_intensity: 3
  proactive_messaging: true

work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1, 2, 3, 4, 5]

schedules:
  daily_report: "09:00"
  doc_drift_check: "09:00"

doc_sync:
  auto_update_level: "moderate"
  github_docs_path: "docs/prd/"
""",
        encoding="utf-8",
    )
    return config_file
