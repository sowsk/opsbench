# opsbench

A public benchmark for evaluating how well frontier LLMs handle operational tasks. Built by a senior PM, not by an ML lab.

v0.1 scores one task: **alert summarization**. Given a raw observability alert plus 5 minutes of preceding context, can a model produce a 2-sentence executive summary that is factually accurate, action-oriented, and does not invent things that were not in the input.

## Why this exists

Foundation model benchmarks measure code, math, reasoning, and general knowledge. None of them measure the work that on-call engineers actually do at 3am: read a noisy alert, ignore the boilerplate, summarize what matters, suggest the next step. Operational AI (AIOps, SRE assistants, NOC copilots) is shipping fast inside Datadog, PagerDuty, BigPanda, Splunk, and nobody has a public number to point at.

This benchmark gives anyone shipping an LLM-backed operational tool a reproducible way to measure quality on the actual task, not a proxy.

## Leaderboard

<!-- LEADERBOARD:START -->
*Placeholder until the first run lands. Re-run any time with `python -m src.run_bench` then `python -m src.score_outputs --run-dir runs/<timestamp>` then `python -m src.leaderboard --run-dir runs/<timestamp>`. This block updates in place; do not edit by hand.*

| Rank | Model | Mean score (0-2) | Factual accuracy | Signal/noise | Action orientation | Brevity | No hallucination |
|---|---|---|---|---|---|---|---|
| 1 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
<!-- LEADERBOARD:END -->

## How it works

1. **Scenarios.** `scenarios/` holds 25 synthetic alert payloads across 4 categories (network outage, app perf regression, security event, capacity warning). Each scenario is a JSON file with the raw alert, 5 minutes of preceding context lines, a ground-truth entity set, and a reference summary. See [scenarios/SCHEMA.md](scenarios/SCHEMA.md).
2. **Runner.** `src/run_bench.py` sends each scenario to each model in `--models`, writes one row per (scenario, model) to `runs/<timestamp>/outputs.jsonl`.
3. **Scorer.** `src/score_outputs.py` runs two passes per output. The first is automated (hallucinated entity check, brevity check). The second is LLM-as-judge with **anti-bias model pairing**, where each model under test is judged by a model from a different family (Claude judged by GPT, GPT judged by Claude, Gemini judged by Claude). Writes `scores.jsonl`.
4. **Leaderboard.** `src/leaderboard.py` aggregates `scores.jsonl` into a markdown leaderboard and updates this README in place.

## Rubric

Five dimensions, each scored 0 to 2 by the judge model (see [methodology.md](methodology.md) for full definitions):

| Dimension | What it asks |
|---|---|
| Factual accuracy | Does the summary correctly describe what the alert said? |
| Signal-to-noise | Did the model skip irrelevant context lines and surface the important ones? |
| Action orientation | Does the summary suggest a defensible next step? |
| Brevity | Did the summary stay at or under the 2-sentence cap? |
| No hallucinated entities | Did the model invent host names, IPs, services, or timestamps not in the input? |

The first four are judge-scored. The fifth is automated (regex extraction of named entities from the output, checked against the scenario's entity allow-list).

## Anti-bias judge pairing

LLM-as-judge has a well-known self-preference bias: a model judging its own output scores it higher than another model would. opsbench controls for this by pairing each system-under-test (SUT) with a judge from a different model family.

| SUT | Judge |
|---|---|
| Claude Sonnet 4.6 | GPT-5 |
| Claude Opus 4.8 | GPT-5 |
| GPT-5 | Claude Sonnet 4.6 |
| Gemini 2.5 Pro | Claude Sonnet 4.6 |

## What this benchmark does NOT measure

- **Latency under load.** Single-call benchmark, no concurrency or streaming test.
- **Multi-turn dialogue.** Each scenario is one-shot summarization.
- **Tool use.** Models are not given tools (CMDB lookup, runbook retrieval, etc.). Adding tool use changes the task; planned for v0.3.
- **Real customer data.** Scenarios are synthetic and modeled after public incident reports. No PII or proprietary telemetry. This means the benchmark cannot distinguish models that pattern-match well on public incident vocabulary from models that would handle a novel real-world payload.
- **Cost-quality tradeoff.** Reported tokens and cost are informational; the ranking does not penalize expensive models.

## Install and reproduce

```bash
git clone https://github.com/sowsk/opsbench.git
cd opsbench
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY

python -m src.run_bench --models claude-sonnet-4-6,claude-opus-4-8,gpt-5,gemini-2.5-pro
python -m src.score_outputs --run-dir runs/<timestamp>
python -m src.leaderboard --run-dir runs/<timestamp>
```

A full v0.1 run (25 scenarios x 4 models x 1 judge call each) costs roughly $2 to $4 depending on model mix and finishes in 8 to 12 minutes.

## What is surprising so far

Filled in after the first published run. One bullet per surprise. Be honest, including surprises that flatter your favorite model less than expected.

## Related work and inspiration

- [Hamel Husain on evals](https://hamel.dev/blog/posts/evals/) — the core methodology this benchmark follows.
- [agentic-pm-workflow/evals/peer-review](https://github.com/sowsk/agentic-pm-workflow/tree/main/evals/peer-review) — the eval suite this benchmark's runner and scorer were adapted from.
- [SWE-bench](https://www.swebench.com/), [MTEB](https://huggingface.co/spaces/mteb/leaderboard), [HumanEval](https://github.com/openai/human-eval) — public benchmarks for adjacent capabilities. opsbench fills the operational gap none of them cover.

## License

MIT.

## About

Built by [Sowmya Krishnamoorthy](https://www.linkedin.com/in/sowmya-krishnamoorthy), senior PM at ThousandEyes (Cisco). I own the alerts, integrations, and dashboards platforms, plus the AI / agentic strategy across them. I shipped Adaptive Alert Detection (77 percent fewer flapping alerts across 826 production orgs) and built an internal Claude-powered alert optimization tool. Real alert summarization is harder than benchmarks suggest. opsbench is my attempt to put a public number on it.

If you ship operational AI, fork this and add scenarios from your domain. PRs welcome.
