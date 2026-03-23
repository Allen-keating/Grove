"""Load and validate .grove/config.yml with env var resolution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class ProjectConfig(BaseModel):
    name: str
    repo: str
    language: str = "zh-CN"


class LarkConfig(BaseModel):
    app_id: str
    app_secret: str
    chat_id: str
    space_id: str


class GitHubConfig(BaseModel):
    app_id: str
    private_key_path: str
    installation_id: str
    webhook_secret: str = ""


class LLMConfig(BaseModel):
    api_key: str
    model: str = "claude-sonnet-4-6"


class PersonaConfig(BaseModel):
    name: str = "Grove"
    tone: str = "专业但不刻板"
    reminder_intensity: int = 3
    proactive_messaging: bool = True


class WorkHoursConfig(BaseModel):
    start: str = "09:00"
    end: str = "18:00"
    timezone: str = "Asia/Shanghai"
    workdays: list[int] = [1, 2, 3, 4, 5]


class SchedulesConfig(BaseModel):
    daily_report: str = "09:00"
    doc_drift_check: str = "09:00"
    project_overview: str = "10:00"
    morning_dispatch: str = "09:15"


class DocSyncConfig(BaseModel):
    auto_update_level: str = "moderate"
    github_docs_path: str = "docs/prd/"


class DispatchConfig(BaseModel):
    confirm_deadline_minutes: int = 75
    max_negotiate_rounds: int = 10


class ModulesConfig(BaseModel):
    """Control which modules are enabled. All enabled by default."""
    communication: bool = True
    prd_generator: bool = True
    task_breakdown: bool = True
    daily_report: bool = True
    pr_review: bool = True
    doc_sync: bool = True
    member: bool = True
    project_scanner: bool = True
    project_overview: bool = True
    morning_dispatch: bool = True


class GroveConfig(BaseModel):
    version: int = 1
    project: ProjectConfig
    lark: LarkConfig
    github: GitHubConfig
    llm: LLMConfig
    persona: PersonaConfig = PersonaConfig()
    work_hours: WorkHoursConfig = WorkHoursConfig()
    schedules: SchedulesConfig = SchedulesConfig()
    doc_sync: DocSyncConfig = DocSyncConfig()
    modules: ModulesConfig = ModulesConfig()
    admin_token: str = ""  # Empty = admin endpoints not mounted
    dispatch: DispatchConfig = DispatchConfig()


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(obj: Any) -> Any:
    if isinstance(obj, str):
        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return _ENV_VAR_PATTERN.sub(replacer, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(grove_dir: str | Path) -> GroveConfig:
    config_path = Path(grove_dir) / "config.yml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    resolved = _resolve_env_vars(raw)
    return GroveConfig(**resolved)
