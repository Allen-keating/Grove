import json
from pathlib import Path

import pytest

from grove.core.storage import Storage


class TestStorage:
    def test_read_yaml(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        data = storage.read_yaml("team.yml")
        assert data["version"] == 1
        assert len(data["team"]) == 3
        assert data["team"][0]["github"] == "zhangsan"

    def test_read_yaml_missing_file(self, grove_dir: Path):
        storage = Storage(grove_dir)
        with pytest.raises(FileNotFoundError):
            storage.read_yaml("nonexistent.yml")

    def test_write_yaml(self, grove_dir: Path):
        storage = Storage(grove_dir)
        data = {"key": "value", "list": [1, 2, 3]}
        storage.write_yaml("test.yml", data)
        result = storage.read_yaml("test.yml")
        assert result == data

    def test_read_json(self, grove_dir: Path):
        storage = Storage(grove_dir)
        data = {"count": 42, "items": ["a", "b"]}
        (grove_dir / "test.json").write_text(json.dumps(data), encoding="utf-8")
        result = storage.read_json("test.json")
        assert result == data

    def test_write_json(self, grove_dir: Path):
        storage = Storage(grove_dir)
        data = {"count": 42, "items": ["a", "b"]}
        storage.write_json("memory/snapshots/2026-03-21.json", data)
        result = storage.read_json("memory/snapshots/2026-03-21.json")
        assert result == data

    def test_write_json_creates_parent_dirs(self, grove_dir: Path):
        storage = Storage(grove_dir)
        storage.write_json("new/nested/dir/data.json", {"ok": True})
        assert (grove_dir / "new" / "nested" / "dir" / "data.json").exists()

    def test_append_jsonl(self, grove_dir: Path):
        storage = Storage(grove_dir)
        storage.append_jsonl("logs/events.jsonl", {"event": "a"})
        storage.append_jsonl("logs/events.jsonl", {"event": "b"})
        lines = (grove_dir / "logs" / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"event": "a"}
        assert json.loads(lines[1]) == {"event": "b"}

    def test_exists(self, grove_dir: Path, sample_team_yml: Path):
        storage = Storage(grove_dir)
        assert storage.exists("team.yml") is True
        assert storage.exists("nonexistent.yml") is False
