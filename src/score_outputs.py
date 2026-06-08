"""Score opsbench outputs from a run directory.

Two-pass scoring:
1. Automated: hallucinated-entity check (regex-based), basic shape checks.
2. LLM-as-judge: factual_accuracy, signal_to_noise, action_orientation, brevity.

Anti-bias pairing: each system-under-test is judged by a model from a
different family. Defined in JUDGE_PAIRING below.

Usage:
    python -m src.score_outputs --run-dir runs/2026-06-08_120000
    python -m src.score_outputs --run-dir <dir> --skip-judge   # automated only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
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
JUDGE_PROMPT_PATH = HERE / "prompts" / "judge_prompt.md"

# SUT -> judge mapping. Each SUT is judged by a model from a different family
# to control for self-preference bias. Keep this list explicit; do not infer.
#
# v0.1 ships a two-family scheme (Anthropic + Google). v0.2 will add OpenAI
# once a personal key is available; the commented entries below are the
# intended additions at that point.
JUDGE_PAIRING: dict[str, str] = {
    "claude-sonnet-4-6": "gemini-2.5-pro",
    "claude-opus-4-8": "gemini-2.5-pro",
    "gemini-2.5-pro": "claude-sonnet-4-6",
    # v0.2 additions (uncomment when GPT-5 is added back to DEFAULT_MODELS):
    # "gpt-5": "claude-sonnet-4-6",
    # "gpt-5-mini": "claude-sonnet-4-6",
    # "gemini-2.5-flash": "claude-sonnet-4-6",
}

# Regex patterns for hallucinated-entity check. Conservative on purpose.
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HOSTNAME_PATTERN = re.compile(
    r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+\b",
    re.IGNORECASE,
)
TIMESTAMP_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?\b")


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def load_scenarios() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(SCENARIOS_DIR.rglob("*.json")):
        with path.open() as f:
            scenario = json.load(f)
            out[scenario["id"]] = scenario
    return out


def extract_entities(text: str) -> dict[str, list[str]]:
    """Pull IP addresses, hostnames, and timestamps from the model output."""
    return {
        "ips": IP_PATTERN.findall(text),
        "hostnames": [h.lower() for h in HOSTNAME_PATTERN.findall(text)],
        "timestamps": TIMESTAMP_PATTERN.findall(text),
    }


def hallucinated_entities(output: str, scenario: dict) -> dict[str, list[str]]:
    """Find entities in the output that are not in the scenario allow-list."""
    allowed = scenario.get("entities", {})
    allowed_ips = {ip.lower() for ip in allowed.get("ips", [])}
    allowed_hostnames = {h.lower() for h in allowed.get("hostnames", [])}
    allowed_timestamps = {t for t in allowed.get("timestamps", [])}

    extracted = extract_entities(output)

    hallucinated_ips = [ip for ip in extracted["ips"] if ip.lower() not in allowed_ips]
    hallucinated_hostnames = [
        h for h in extracted["hostnames"]
        if h not in allowed_hostnames and not any(h in allowed_h or allowed_h in h for allowed_h in allowed_hostnames)
    ]
    hallucinated_timestamps = [t for t in extracted["timestamps"] if t not in allowed_timestamps]

    return {
        "ips": list(set(hallucinated_ips)),
        "hostnames": list(set(hallucinated_hostnames)),
        "timestamps": list(set(hallucinated_timestamps)),
    }


def sentence_count(text: str) -> int:
    # Strip common abbreviations before counting.
    cleaned = re.sub(r"\b(e\.g|i\.e|etc|vs|Mr|Mrs|Dr|St)\.", r"\1", text)
    sentences = [s for s in re.split(r"[.!?]+\s+", cleaned.strip()) if s.strip()]
    # If the text does not end with terminal punctuation, the last fragment still counts.
    return max(1, len(sentences)) if cleaned.strip() else 0


def automated_scores(scenario: dict, run_record: dict) -> dict:
    output = run_record.get("output") or ""
    hallucinated = hallucinated_entities(output, scenario)
    any_hallucinated = any(hallucinated.values())
    return {
        "sentence_count": sentence_count(output),
        "char_count": len(output),
        "word_count": len(output.split()),
        "hallucinated_entities": hallucinated,
        "any_hallucinated": any_hallucinated,
        "no_hallucination_score": 0 if any_hallucinated else 2,
    }


def build_judge_user_message(scenario: dict, model_output: str) -> str:
    return (
        f"SCENARIO_ID: {scenario['id']}\n"
        f"CATEGORY: {scenario['category']}\n"
        f"SEVERITY: {scenario.get('severity', 'unknown')}\n\n"
        f"ALERT:\n{scenario['alert']}\n\n"
        f"CONTEXT (indices match noise_lines):\n"
        + "\n".join(f"[{i}] {line}" for i, line in enumerate(scenario.get("context", [])))
        + "\n\n"
        f"NOISE_LINES (indices that are deliberately irrelevant): {scenario.get('noise_lines', [])}\n\n"
        f"REFERENCE_SUMMARY (one valid answer, not the only one):\n{scenario.get('reference_summary', '(none)')}\n\n"
        f"REFERENCE_ACTION:\n{scenario.get('reference_action', '(none)')}\n\n"
        f"MODEL_OUTPUT:\n{model_output}\n\n"
        f"Score per the system prompt. Return only JSON."
    )


def run_judge(judge_model: str, judge_system: str, scenario: dict, model_output: str) -> dict:
    user_msg = build_judge_user_message(scenario, model_output)
    resp = call_model(judge_model, judge_system, user_msg, max_tokens=1024)
    if resp.error:
        return {"judge_model": judge_model, "judge_scores": None, "judge_error": resp.error}

    raw = resp.output_text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n", "", raw)
        raw = re.sub(r"\n```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "judge_model": judge_model,
            "judge_scores": None,
            "judge_raw": resp.output_text,
            "judge_error": f"JSONDecodeError: {exc}",
        }

    return {
        "judge_model": judge_model,
        "judge_scores": parsed,
        "judge_input_tokens": resp.input_tokens,
        "judge_output_tokens": resp.output_tokens,
        "judge_cost_usd": resp.cost_usd,
        "judge_error": None,
    }


def aggregate_by_model(scores: list[dict]) -> dict[str, dict]:
    """Compute mean dimension scores and overall mean per model."""
    by_model: dict[str, list[dict]] = defaultdict(list)
    for s in scores:
        by_model[s["model"]].append(s)

    out: dict[str, dict] = {}
    for model, model_scores in by_model.items():
        n = len(model_scores)
        if n == 0:
            continue

        dim_sums = {
            "factual_accuracy": 0.0,
            "signal_to_noise": 0.0,
            "action_orientation": 0.0,
            "brevity": 0.0,
        }
        no_hallucination_sum = 0.0
        judge_failures = 0

        for s in model_scores:
            auto = s["automated"]
            no_hallucination_sum += auto["no_hallucination_score"]
            judge = s.get("judge", {}).get("judge_scores")
            if not judge or not isinstance(judge, dict) or "scores" not in judge:
                judge_failures += 1
                continue
            for dim in dim_sums:
                val = judge["scores"].get(dim)
                if isinstance(val, (int, float)):
                    dim_sums[dim] += val

        judged = n - judge_failures
        means = {dim: (dim_sums[dim] / judged if judged else 0.0) for dim in dim_sums}
        means["no_hallucinated_entities"] = no_hallucination_sum / n
        mean_total = sum(means.values()) / len(means)

        out[model] = {
            "n": n,
            "judged_n": judged,
            "judge_failures": judge_failures,
            "dimension_means": means,
            "mean_score": round(mean_total, 3),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Score opsbench outputs.")
    parser.add_argument("--run-dir", required=True, help="Directory with outputs.jsonl")
    parser.add_argument("--skip-judge", action="store_true", help="Skip LLM judge, automated only")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    outputs_path = run_dir / "outputs.jsonl"
    if not outputs_path.exists():
        print(f"Outputs file not found: {outputs_path}")
        return 2

    scenarios = load_scenarios()
    outputs = load_jsonl(outputs_path)
    judge_system = JUDGE_PROMPT_PATH.read_text() if not args.skip_judge else ""

    scores: list[dict] = []
    total = len(outputs)
    print(f"Scoring {total} outputs from {run_dir}")

    for i, run_record in enumerate(outputs, 1):
        scenario_id = run_record["scenario_id"]
        scenario = scenarios.get(scenario_id)
        if not scenario:
            print(f"  [{i}/{total}] {scenario_id} - scenario not found, skipping")
            continue

        sut_model = run_record["model"]
        auto = automated_scores(scenario, run_record)
        entry: dict = {
            "scenario_id": scenario_id,
            "category": scenario["category"],
            "model": sut_model,
            "automated": auto,
        }

        if not args.skip_judge and not run_record.get("error"):
            judge_model = JUDGE_PAIRING.get(sut_model)
            if not judge_model:
                print(f"  [{i}/{total}] {scenario_id}/{sut_model} - no judge pairing defined, skipping judge")
                entry["judge"] = {"judge_error": f"no JUDGE_PAIRING entry for {sut_model}"}
            else:
                print(f"  [{i}/{total}] {scenario_id}/{sut_model} judged by {judge_model} ... ", end="", flush=True)
                judge_result = run_judge(judge_model, judge_system, scenario, run_record["output"])
                entry["judge"] = judge_result
                if judge_result.get("judge_error"):
                    print(f"JUDGE ERROR: {judge_result['judge_error']}")
                else:
                    js = judge_result["judge_scores"]["scores"]
                    print(f"f={js['factual_accuracy']} s={js['signal_to_noise']} a={js['action_orientation']} b={js['brevity']}")
        elif run_record.get("error"):
            print(f"  [{i}/{total}] {scenario_id}/{sut_model} - SUT errored, skipping judge")

        scores.append(entry)

    scores_path = run_dir / "scores.jsonl"
    with scores_path.open("w") as f:
        for s in scores:
            f.write(json.dumps(s) + "\n")
    print(f"\nWrote {scores_path}")

    by_model = aggregate_by_model(scores)
    summary_path = run_dir / "summary.json"
    with summary_path.open("w") as f:
        json.dump(by_model, f, indent=2)
    print(f"Wrote {summary_path}")

    print("\nPer-model mean scores:")
    for model, agg in sorted(by_model.items(), key=lambda kv: -kv[1]["mean_score"]):
        print(f"  {model:30s} mean={agg['mean_score']:.2f}  n={agg['n']}  judge_failures={agg['judge_failures']}")

    print()
    print(f"Next: python -m src.leaderboard --run-dir {run_dir.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
