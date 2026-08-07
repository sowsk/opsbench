"""Copy a completed run into the version-controlled published-runs tree."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RUNS_DIR = REPO_ROOT / "runs"
REQUIRED_ARTIFACTS = ("outputs.jsonl", "scores.jsonl", "summary.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish reproducible OpsBench run artifacts.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--runner-commit", required=True)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    source = Path(args.run_dir)
    if not source.is_absolute():
        source = REPO_ROOT / source
    missing = [name for name in REQUIRED_ARTIFACTS if not (source / name).exists()]
    if missing:
        print(f"Cannot publish; missing: {', '.join(missing)}")
        return 2

    destination = RUNS_DIR / "published" / source.name
    destination.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_ARTIFACTS:
        shutil.copy2(source / name, destination / name)

    outputs = [json.loads(line) for line in (source / "outputs.jsonl").read_text().splitlines() if line]
    scores = [json.loads(line) for line in (source / "scores.jsonl").read_text().splitlines() if line]
    manifest = {
        "run": source.name,
        "published_on": date.today().isoformat(),
        "runner_commit": args.runner_commit,
        "scorer_commit": "commit containing this published artifact",
        "models": sorted({row["model"] for row in outputs}),
        "judge_models": sorted({row.get("judge", {}).get("judge_model") for row in scores if row.get("judge", {}).get("judge_model")}),
        "scenario_count": len({row["scenario_id"] for row in outputs}),
        "output_count": len(outputs),
        "sut_cost_usd": round(sum(row.get("cost_usd", 0.0) for row in outputs), 6),
        "judge_cost_usd": round(sum(row.get("judge", {}).get("judge_cost_usd", 0.0) for row in scores), 6),
        "note": args.note,
    }
    (destination / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Published artifacts to {destination.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
