"""File storage utilities for reading/writing .grove/ directory."""

import json
from pathlib import Path
from typing import Any

import yaml


class Storage:
    """Read and write YAML/JSON files under a .grove/ directory."""

    def __init__(self, grove_dir: str | Path):
        self.root = Path(grove_dir)

    def _resolve(self, relative_path: str) -> Path:
        return self.root / relative_path

    def read_yaml(self, relative_path: str) -> dict[str, Any]:
        path = self._resolve(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def write_yaml(self, relative_path: str, data: dict[str, Any]) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self._resolve(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, relative_path: str, data: dict[str, Any]) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def append_jsonl(self, relative_path: str, data: dict[str, Any]) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()
