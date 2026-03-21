# tests/test_core/test_config.py
from pathlib import Path
import pytest
from grove.config import load_config


class TestConfig:
    def test_load_config(self, grove_dir: Path, sample_config_yml: Path):
        config = load_config(grove_dir)
        assert config.project.name == "Test Project"
        assert config.project.repo == "testorg/testrepo"
        assert config.lark.app_id == "test_app_id"
        assert config.github.app_id == "12345"
        assert config.llm.model == "claude-sonnet-4-6"
        assert config.persona.name == "Grove"
        assert config.work_hours.timezone == "Asia/Shanghai"
        assert config.schedules.daily_report == "09:00"
        assert config.doc_sync.auto_update_level == "moderate"

    def test_load_config_missing_file(self, grove_dir: Path):
        with pytest.raises(FileNotFoundError):
            load_config(grove_dir)

    def test_config_env_var_resolution(self, grove_dir: Path, monkeypatch):
        monkeypatch.setenv("LARK_APP_ID", "env_resolved_id")
        config_file = grove_dir / "config.yml"
        config_file.write_text(
            """\
version: 1
project:
  name: "Test"
  repo: "org/repo"
  language: "zh-CN"
lark:
  app_id: "${LARK_APP_ID}"
  app_secret: "secret"
  chat_id: "oc_test"
  space_id: "spc_test"
github:
  app_id: "123"
  private_key_path: "/tmp/key.pem"
  installation_id: "456"
  webhook_secret: "ws"
llm:
  api_key: "key"
  model: "claude-sonnet-4-6"
persona:
  name: "Grove"
  tone: "professional"
  reminder_intensity: 3
  proactive_messaging: true
work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1,2,3,4,5]
schedules:
  daily_report: "09:00"
  doc_drift_check: "09:00"
doc_sync:
  auto_update_level: "moderate"
  github_docs_path: "docs/prd/"
""",
            encoding="utf-8",
        )
        config = load_config(grove_dir)
        assert config.lark.app_id == "env_resolved_id"
