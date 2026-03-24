from grove.modules.prd_baseline.baseline_editor import (
    parse_features, append_feature, move_feature, format_feature_entry,
)

SAMPLE_BASELINE = """\
# TestProject 项目基线文档

## 功能清单

### ✅ 已实现
- ✅ **用户登录** — OAuth2 登录 `#PR-12`

### 🔄 进行中
- 🔄 **数据导出** — CSV 导出 → [详细 PRD](prd-数据导出.md)

### ⬚ 待开发
- ⬚ **仪表盘** — 数据可视化 → [详细 PRD](prd-仪表盘.md)

## 里程碑
"""


class TestParseFeatures:
    def test_parses_all_sections(self):
        result = parse_features(SAMPLE_BASELINE)
        assert len(result["done"]) == 1
        assert result["done"][0]["name"] == "用户登录"
        assert len(result["in_progress"]) == 1
        assert result["in_progress"][0]["name"] == "数据导出"
        assert len(result["planned"]) == 1
        assert result["planned"][0]["name"] == "仪表盘"

    def test_empty_sections(self):
        content = "# Doc\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n"
        result = parse_features(content)
        assert result == {"done": [], "in_progress": [], "planned": []}


class TestAppendFeature:
    def test_append_to_planned(self):
        entry = format_feature_entry("反馈系统", "用户反馈", "planned", prd_path="prd-反馈系统.md")
        result = append_feature(SAMPLE_BASELINE, "planned", entry)
        assert "反馈系统" in result
        assert result.index("反馈系统") > result.index("仪表盘")

    def test_append_to_empty_section(self):
        content = "# Doc\n\n## 功能清单\n\n### ✅ 已实现\n\n### 🔄 进行中\n\n### ⬚ 待开发\n\n## 里程碑\n"
        entry = format_feature_entry("新功能", "描述", "planned")
        result = append_feature(content, "planned", entry)
        assert "新功能" in result


class TestMoveFeature:
    def test_move_planned_to_in_progress(self):
        result = move_feature(SAMPLE_BASELINE, "仪表盘", "planned", "in_progress")
        features = parse_features(result)
        assert any(f["name"] == "仪表盘" for f in features["in_progress"])
        assert not any(f["name"] == "仪表盘" for f in features["planned"])

    def test_move_in_progress_to_done(self):
        result = move_feature(SAMPLE_BASELINE, "数据导出", "in_progress", "done")
        features = parse_features(result)
        assert any(f["name"] == "数据导出" for f in features["done"])
        assert not any(f["name"] == "数据导出" for f in features["in_progress"])

    def test_move_nonexistent_returns_unchanged(self):
        result = move_feature(SAMPLE_BASELINE, "不存在", "planned", "done")
        assert result == SAMPLE_BASELINE


class TestFormatFeatureEntry:
    def test_planned_with_prd(self):
        entry = format_feature_entry("反馈系统", "反馈收集", "planned", prd_path="prd-反馈系统.md")
        assert entry == "- ⬚ **反馈系统** — 反馈收集 → [详细 PRD](prd-反馈系统.md)"

    def test_done_with_pr(self):
        entry = format_feature_entry("登录", "OAuth 登录", "done", pr_number=42)
        assert entry == "- ✅ **登录** — OAuth 登录 `#PR-42`"

    def test_in_progress_minimal(self):
        entry = format_feature_entry("搜索", "全文搜索", "in_progress")
        assert entry == "- 🔄 **搜索** — 全文搜索"
