"""Validate scenario files without making API calls."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"
REQUIRED_FIELDS = {
    "id",
    "category",
    "title",
    "severity",
    "alert",
    "context",
    "noise_lines",
    "entities",
    "reference_summary",
    "reference_action",
}
VALID_CATEGORIES = {
    "network-outage",
    "compute-fabric",
    "app-perf-regression",
    "security-event",
    "capacity-warning",
}
ID_PATTERN = re.compile(r"^(?P<category>[a-z-]+)-(?P<number>\d{3})-(?P<slug>[a-z0-9-]+)$")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        scenario = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: invalid JSON: {exc}"]

    missing = sorted(REQUIRED_FIELDS - scenario.keys())
    if missing:
        errors.append(f"{path}: missing fields: {', '.join(missing)}")

    scenario_id = scenario.get("id", "")
    match = ID_PATTERN.fullmatch(scenario_id)
    if not match:
        errors.append(f"{path}: invalid id {scenario_id!r}")
    else:
        if match.group("category") != scenario.get("category"):
            errors.append(f"{path}: id category does not match category field")
        expected_name = f"{match.group('number')}-{match.group('slug')}.json"
        if path.name != expected_name:
            errors.append(f"{path}: filename should be {expected_name}")

    category = scenario.get("category")
    if category not in VALID_CATEGORIES:
        errors.append(f"{path}: unknown category {category!r}")
    elif path.parent.name != category:
        errors.append(f"{path}: parent directory does not match category")

    context = scenario.get("context")
    if not isinstance(context, list) or not context:
        errors.append(f"{path}: context must be a non-empty list")
        context = []

    noise_lines = scenario.get("noise_lines")
    if not isinstance(noise_lines, list) or not noise_lines:
        errors.append(f"{path}: noise_lines must be a non-empty list")
    elif any(not isinstance(i, int) or i < 0 or i >= len(context) for i in noise_lines):
        errors.append(f"{path}: noise_lines contains an invalid context index")

    entities = scenario.get("entities")
    if not isinstance(entities, dict):
        errors.append(f"{path}: entities must be an object")

    if scenario.get("severity") not in {"critical", "high", "medium", "low"}:
        errors.append(f"{path}: invalid severity {scenario.get('severity')!r}")

    return errors


def main() -> int:
    paths = sorted(SCENARIOS_DIR.rglob("*.json"))
    errors: list[str] = []
    seen_ids: set[str] = set()
    for path in paths:
        errors.extend(validate_file(path))
        try:
            scenario_id = json.loads(path.read_text()).get("id")
        except (OSError, json.JSONDecodeError):
            continue
        if scenario_id in seen_ids:
            errors.append(f"{path}: duplicate id {scenario_id!r}")
        seen_ids.add(scenario_id)

    if errors:
        print("Scenario validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validated {len(paths)} scenarios across {len({p.parent.name for p in paths})} categories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
