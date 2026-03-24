"""Deterministic Markdown operations for the project baseline document."""
import re

_STATUS_ICONS = {"done": "✅", "in_progress": "🔄", "planned": "⬚"}
_SECTION_HEADERS = {
    "done": "### ✅ 已实现",
    "in_progress": "### 🔄 进行中",
    "planned": "### ⬚ 待开发",
}
_FEATURE_RE = re.compile(
    r"^- [✅🔄⬚] \*\*(.+?)\*\* — (.+)$"
)


def parse_features(baseline_content: str) -> dict[str, list[dict]]:
    """Parse the feature list sections from baseline Markdown."""
    result: dict[str, list[dict]] = {"done": [], "in_progress": [], "planned": []}
    current_section: str | None = None

    for line in baseline_content.split("\n"):
        stripped = line.strip()
        if stripped == _SECTION_HEADERS["done"]:
            current_section = "done"
        elif stripped == _SECTION_HEADERS["in_progress"]:
            current_section = "in_progress"
        elif stripped == _SECTION_HEADERS["planned"]:
            current_section = "planned"
        elif stripped.startswith("## ") or stripped.startswith("### "):
            current_section = None
        elif current_section and (m := _FEATURE_RE.match(stripped)):
            result[current_section].append({
                "name": m.group(1),
                "description": m.group(2),
                "raw_line": stripped,
            })

    return result


def format_feature_entry(
    name: str, description: str, status: str,
    prd_path: str | None = None, pr_number: int | None = None,
) -> str:
    """Generate a standard-format feature entry line."""
    icon = _STATUS_ICONS.get(status, "❓")
    entry = f"- {icon} **{name}** — {description}"
    if prd_path:
        entry += f" → [详细 PRD]({prd_path})"
    elif pr_number:
        entry += f" `#PR-{pr_number}`"
    return entry


def append_feature(baseline_content: str, section: str, entry: str) -> str:
    """Append a feature entry to the end of a section."""
    header = _SECTION_HEADERS.get(section)
    if not header:
        return baseline_content

    lines = baseline_content.split("\n")
    result = []
    found_section = False
    inserted = False

    for i, line in enumerate(lines):
        result.append(line)
        if line.strip() == header:
            found_section = True
            continue
        if found_section and not inserted:
            # Check if next line is a new heading (end of section)
            is_next_heading = (
                i + 1 < len(lines) and
                (lines[i + 1].strip().startswith("### ") or lines[i + 1].strip().startswith("## "))
            )
            is_last_content = not line.strip() and is_next_heading

            if is_last_content or is_next_heading:
                result.insert(len(result) - 1 if is_last_content else len(result), entry)
                inserted = True

    if found_section and not inserted:
        # Section was at the end of file or had no items
        result.append(entry)

    return "\n".join(result)


def move_feature(
    baseline_content: str, feature_name: str,
    from_section: str, to_section: str,
) -> str:
    """Move a feature from one section to another, updating the status icon."""
    features = parse_features(baseline_content)
    source_features = features.get(from_section, [])
    match = next((f for f in source_features if f["name"] == feature_name), None)
    if not match:
        return baseline_content

    # Remove from source
    content = baseline_content.replace(match["raw_line"] + "\n", "")
    content = content.replace(match["raw_line"], "")  # handle last line without newline

    # Build new entry with updated icon
    new_entry = format_feature_entry(
        name=match["name"],
        description=match["description"].split(" → ")[0].split(" `")[0],
        status=to_section,
    )

    # Append to target
    return append_feature(content, to_section, new_entry)
