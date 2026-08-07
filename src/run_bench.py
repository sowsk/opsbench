"""Run opsbench scenarios against one or more models.

Loads every JSON file under scenarios/, sends each to each model, writes
outputs.jsonl to runs/<timestamp>/.

Usage:
    python -m src.run_bench
    python -m src.run_bench --models claude-sonnet-5,gpt-5.6-terra,gemini-3.6-flash
    python -m src.run_bench --scenarios network-outage-001-bgp-flap
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .models import call_model

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"
SYSTEM_PROMPT_PATH = HERE / "prompts" / "system_prompt.md"
RUNS_DIR = REPO_ROOT / "runs"

# One current, balanced model per provider. Historical published runs retain
# their exact model IDs in their run artifacts.
DEFAULT_MODELS = "claude-sonnet-5,gpt-5.6-terra,gemini-3.6-flash"


def load_scenarios(scenario_ids: list[str] | None = None) -> list[dict]:
    scenarios: list[dict] = []
    for path in sorted(SCENARIOS_DIR.rglob("*.json")):
        with path.open() as f:
            scenarios.append(json.load(f))
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [s for s in scenarios if s["id"] in wanted]
        missing = wanted - {s["id"] for s in scenarios}
        if missing:
            print(f"Warning: requested scenarios not found: {sorted(missing)}")
    return scenarios


def build_user_message(scenario: dict) -> str:
    parts = [
        "ALERT:",
        scenario["alert"],
        "",
        "CONTEXT (preceding 5 to 15 minutes, newest last):",
    ]
    for i, line in enumerate(scenario.get("context", [])):
        parts.append(f"[{i}] {line}")
    return "\n".join(parts)


def resolve_out_dir(value: str | None, timestamp: str) -> Path:
    """Resolve relative output paths from the repository root."""
    path = Path(value) if value else RUNS_DIR / timestamp
    return path if path.is_absolute() else REPO_ROOT / path


def display_path(path: Path) -> str:
    """Prefer a repository-relative path, while allowing external paths."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run opsbench scenarios against one or more models.")
    parser.add_argument("--models", default=DEFAULT_MODELS,
                        help=f"Comma-separated model IDs (default: {DEFAULT_MODELS})")
    parser.add_argument("--scenarios", default=None,
                        help="Comma-separated scenario IDs to run (default: all)")
    parser.add_argument("--out-dir", default=None, help="Output dir (default: runs/<timestamp>)")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    scenario_ids = [s.strip() for s in args.scenarios.split(",")] if args.scenarios else None
    scenarios = load_scenarios(scenario_ids)
    if not scenarios:
        print("No scenarios loaded. Add JSON files under scenarios/<category>/.")
        return 2

    system_prompt = SYSTEM_PROMPT_PATH.read_text()

    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = resolve_out_dir(args.out_dir, timestamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs_path = out_dir / "outputs.jsonl"

    total = len(scenarios) * len(models)
    print(f"Running {len(scenarios)} scenarios x {len(models)} models = {total} calls")
    print(f"Writing to {outputs_path}")

    failures = 0
    with outputs_path.open("w") as f:
        i = 0
        for scenario in scenarios:
            user_msg = build_user_message(scenario)
            for model in models:
                i += 1
                print(f"  [{i}/{total}] {scenario['id']} -> {model} ... ", end="", flush=True)
                resp = call_model(model, system_prompt, user_msg)
                record = {
                    "scenario_id": scenario["id"],
                    "category": scenario["category"],
                    "model": model,
                    "output": resp.output_text,
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                    "elapsed_ms": resp.elapsed_ms,
                    "cost_usd": resp.cost_usd,
                    "error": resp.error,
                }
                f.write(json.dumps(record) + "\n")
                f.flush()
                if resp.error:
                    print(f"ERROR: {resp.error}")
                    failures += 1
                else:
                    print(f"ok ({resp.output_tokens} tok, {resp.elapsed_ms} ms, ${resp.cost_usd:.4f})")

    print()
    print(f"Done. {total - failures}/{total} calls succeeded.")
    print(f"Outputs: {outputs_path}")
    print()
    if failures:
        print("Resolve the provider errors above before scoring this run.")
        return 1
    print(f"Next: python -m src.score_outputs --run-dir {display_path(out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
