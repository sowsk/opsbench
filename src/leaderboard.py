"""Build a leaderboard from a scored run and update README.md in place.

Reads summary.json (produced by score_outputs.py), renders a markdown
leaderboard table, and replaces the leaderboard block in README.md.

The leaderboard block is delimited by markers so the rest of the README is
preserved exactly. Add these markers in README.md once:

    <!-- LEADERBOARD:START -->
    ...table content gets replaced...
    <!-- LEADERBOARD:END -->

Usage:
    python -m src.leaderboard --run-dir runs/2026-06-08_120000
    python -m src.leaderboard --run-dir <dir> --print-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
README_PATH = REPO_ROOT / "README.md"

START_MARKER = "<!-- LEADERBOARD:START -->"
END_MARKER = "<!-- LEADERBOARD:END -->"


def build_table(summary: dict, run_label: str, run_path: str | None = None, note: str = "") -> str:
    rows = sorted(summary.items(), key=lambda kv: -kv[1]["mean_score"])
    lines = [
        f"## Leaderboard ({run_label})",
        "",
        "| Rank | Model | Mean quality (0-2) | Factual accuracy | Signal/noise | Action orientation | Brevity | No hallucination | Median observed latency | Avg cost/scenario |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for rank, (model, agg) in enumerate(rows, 1):
        d = agg["dimension_means"]
        performance = agg.get("performance", {})
        latency = performance.get("median_observed_latency_ms")
        mean_cost = performance.get("mean_cost_usd_per_scenario")
        latency_text = f"{latency / 1000:.2f}s" if isinstance(latency, (int, float)) else "—"
        cost_text = f"${mean_cost:.4f}" if isinstance(mean_cost, (int, float)) else "—"
        lines.append(
            f"| {rank} | `{model}` | **{agg['mean_score']:.2f}** | "
            f"{d['factual_accuracy']:.2f} | {d['signal_to_noise']:.2f} | "
            f"{d['action_orientation']:.2f} | {d['brevity']:.2f} | {d['no_hallucinated_entities']:.2f} | "
            f"{latency_text} | {cost_text} |"
        )
    lines.append("")
    if any(agg["judge_failures"] for _, agg in rows):
        lines.append("> Note: some judge calls failed and were excluded from the dimension means. See the run's scores.jsonl for details.")
        lines.append("")
    artifact_path = run_path or f"runs/{run_label}"
    lines.append(f"Run: `{run_label}`. Artifacts: `{artifact_path}`.")
    lines.append("")
    lines.append("> Quality determines rank. Latency is median end-to-end API time over five sequential calls and includes network/provider overhead; cost is estimated from the recorded tokens and pricing snapshot.")
    if note:
        lines.append("")
        lines.append(f"> Run note: {note}")
    return "\n".join(lines)


def update_readme(table_md: str) -> bool:
    if not README_PATH.exists():
        return False
    text = README_PATH.read_text()
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        return False
    before = text[: start + len(START_MARKER)]
    after = text[end:]
    new_text = f"{before}\n{table_md}\n{after}"
    README_PATH.write_text(new_text)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build leaderboard from a scored run.")
    parser.add_argument("--run-dir", required=True, help="Directory with summary.json")
    parser.add_argument("--print-only", action="store_true", help="Print the leaderboard, do not update README")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        print(f"summary.json not found at {summary_path}. Run score_outputs.py first.")
        return 2

    with summary_path.open() as f:
        summary = json.load(f)
    if not summary:
        print("Empty summary; no models to rank.")
        return 1

    run_label = run_dir.name
    try:
        run_path = str(run_dir.relative_to(REPO_ROOT))
    except ValueError:
        run_path = str(run_dir)
    manifest_path = run_dir / "run.json"
    note = ""
    if manifest_path.exists():
        with manifest_path.open() as f:
            note = json.load(f).get("note", "")
    table_md = build_table(summary, run_label, run_path, note)

    print(table_md)

    if args.print_only:
        return 0

    if update_readme(table_md):
        print(f"\nUpdated leaderboard block in {README_PATH.relative_to(REPO_ROOT)}.")
    else:
        print(
            f"\nLeaderboard markers not found in README.md. Add these two lines around the leaderboard block:\n"
            f"  {START_MARKER}\n  {END_MARKER}\n"
            "Then re-run --no-print-only."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
