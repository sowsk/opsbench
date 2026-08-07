# opsbench

A public benchmark for how well LLMs summarize and reason about operational alerts. Run by a PM who is tired of vendor demos that test only the easy cases.

v0.2 scores one task: **alert summarization**. Given a raw observability alert plus 5 minutes of preceding context, can a frontier LLM produce a 2-sentence summary that is factually accurate, action-oriented, and does not invent things that were not in the input? It reports observed API latency and estimated cost alongside quality rather than blending them into one score.

Three things make opsbench different from the AIOps benchmarks vendors publish in their own white papers:

1. The scoring rubric is public, versioned, and named (factual accuracy, signal-to-noise, action orientation, brevity, no hallucinated entities).
2. Each model under test is judged by a model from a different family, so Claude is not grading itself.
3. The "what this does NOT measure" section is the longest in this README on purpose.

## Current status

v0.2 is a five-scenario pilot across five operational categories and four current models. Its cross-family judge results have **not yet been calibrated against author scoring**, so the leaderboard is useful as a pilot result, not a statistically reliable model ranking. The raw run artifacts are published under [`runs/published/2026-08-07_v0.2`](runs/published/2026-08-07_v0.2), and the remaining calibration work is under [`validation/`](validation/).

## What "good" looks like

Before installing anything, here is one of the five v0.2 scenarios.

**Alert (`network-outage-001-bgp-flap`):**

```
ALERT: BGP_SESSION_DOWN
Device: edge-rtr-01.sfo.prod
Neighbor: 198.51.100.1 (AS 64501, Transit-A)
State transition: Established -> Active
Flap count (last 1h): 7
Impact: 12.4 Gbps shifted to backup transit
```

Plus 9 lines of preceding context, including two deliberately irrelevant lines (a slack message about API latency, a synthetic check still inside SLO). The scenario also includes the change-management entry for a planned MPLS PE upgrade on Transit-A.

**Reference summary the rubric is built around:**

> edge-rtr-01.sfo.prod is flapping its BGP session with Transit-A (AS 64501, neighbor 198.51.100.1) 7 times in the last hour, coinciding with a Transit-A MPLS PE upgrade window (CHG-44218). Traffic has shifted cleanly to edge-rtr-02 and SLOs are intact, so the immediate user impact is contained.

**Reference next action:**

> Contact Transit-A NOC referencing CHG-44218 to confirm whether the flapping is expected during the maintenance window, and consider pre-emptively draining edge-rtr-01 to the backup path if the window extends past 17:00 UTC.

A model that omits CHG-44218, hallucinates a new IP, leads with the slack message, or writes 5 sentences instead of 2 loses points. A model that names the change, ignores the noise, and proposes a defensible next action scores well.

Full scenario format and the other four: [scenarios/SCHEMA.md](scenarios/SCHEMA.md).

## Use this if...

- **You are picking a model for an incident copilot or alert summarizer.** Open the leaderboard, sort by the dimensions you care about (factual accuracy if your concern is trust, brevity if you have a UI constraint), and stop relying on vendor blog posts.
- **You are about to pilot an AI alerting feature.** Run your candidate prompt and model against the suite before you put it in front of an SRE. A failure here identifies a pre-production problem worth investigating; a pass does not prove production readiness.
- **You are evaluating an AIOps vendor.** Ask them to publish their numbers against this benchmark. If they refuse, that is the answer.
- **You are a PM or engineer building eval suites for ops AI.** Use this as a worked example: 5-dimension rubric, cross-family judge pairing, automated plus LLM-as-judge split, and a transparent author-calibration workflow. Fork and adapt.
- **You are an SRE skeptical of "AI for on-call" claims.** Run the suite yourself in 10 minutes for $2. Then form an opinion.

## Leaderboard

<!-- LEADERBOARD:START -->
## Leaderboard (2026-08-07_v0.2)

| Rank | Model | Mean quality (0-2) | Factual accuracy | Signal/noise | Action orientation | Brevity | No hallucination | Median observed latency | Avg cost/scenario |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `gpt-5.6-terra` | **1.96** | 2.00 | 1.80 | 2.00 | 2.00 | 2.00 | 2.40s | $0.0034 |
| 2 | `claude-sonnet-5` | **1.88** | 1.60 | 1.80 | 2.00 | 2.00 | 2.00 | 5.10s | $0.0055 |
| 3 | `claude-opus-5` | **1.76** | 1.20 | 1.80 | 1.80 | 2.00 | 2.00 | 6.45s | $0.0181 |
| 4 | `gemini-3.6-flash` | **1.16** | 1.20 | 0.80 | 0.00 | 1.80 | 2.00 | 3.82s | $0.0021 |

Run: `2026-08-07_v0.2`. Artifacts: `runs/published/2026-08-07_v0.2`.

> Quality determines rank. Latency is median end-to-end API time over five sequential calls and includes network/provider overhead; cost is estimated from the recorded tokens and pricing snapshot.

> Run note: v0.2 pilot: 5 scenarios x 4 current models; quality plus observed API latency and estimated SUT cost; 20/20 judge scores valid after targeted retries; human calibration pending
<!-- LEADERBOARD:END -->

## How it works

1. **Scenarios** in `scenarios/` are five synthetic alert payloads across five categories (network outage, compute fabric, app performance regression, security event, capacity warning). Each JSON file has the raw alert, preceding context, a ground-truth entity set, and a reference summary. See [scenarios/SCHEMA.md](scenarios/SCHEMA.md).
2. **Runner** (`src/run_bench.py`) sends each scenario to each model in `--models`, writes one row per (scenario, model) to `runs/<timestamp>/outputs.jsonl`.
3. **Scorer** (`src/score_outputs.py`) runs two passes per output. Pass 1 is automated (hallucinated-entity check via regex, brevity check). Pass 2 is LLM-as-judge with anti-bias pairing: every model under test is judged by a model from a different family.
4. **Leaderboard** (`src/leaderboard.py`) aggregates `scores.jsonl` into a markdown table and updates this README in place.

Full rubric, validation plan, and known methodology limitations: [methodology.md](methodology.md).

## Install

| Path | Command | Status |
|---|---|---|
| pip (when packaged) | `pip install opsbench` | Not yet packaged |
| uvx (zero-install run) | `uvx opsbench run --models claude-sonnet-5,gpt-5.6-terra` | Planned |
| Clone and venv | see below | Works today |

```bash
git clone https://github.com/sowsk/opsbench.git
cd opsbench
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in the provider keys for the models you want to run

python -m src.validate_scenarios
python -m src.run_bench
python -m src.score_outputs --run-dir runs/<timestamp>
python -m src.leaderboard --run-dir runs/<timestamp>
```

## Bring your own keys

You bring one API key per provider you want to test. Costs are per-provider, no opsbench markup.

The runner supports the historical v0.1-lite models plus these current model tiers. Prices are standard short-context API rates per million input/output tokens, snapshotted on **August 7, 2026**. Sonnet 5 uses Anthropic's introductory $2/$10 rate through August 31, 2026.

| Provider | Models | Input / output per 1M tokens |
|---|---|---|
| Anthropic | `claude-fable-5`; `claude-opus-5`; `claude-sonnet-5` | $10/$50; $5/$25; $2/$10 |
| OpenAI | `gpt-5.6-sol`; `gpt-5.6-terra`; `gpt-5.6-luna` | $5/$30; $2/$12; $0.20/$1.20 |
| Google | `gemini-3.6-flash`; `gemini-3.5-flash-lite`; `gemini-2.5-pro` | $1.50/$7.50; $0.30/$2.50; $1.25/$10 |

Pricing changes over time. Update [the pricing registry](src/models.py) and record a snapshot date before publishing a cost comparison.

Official pricing/model sources: [Anthropic](https://platform.claude.com/docs/en/about-claude/models/overview), [OpenAI](https://developers.openai.com/api/docs/pricing), and [Google](https://ai.google.dev/gemini-api/docs/pricing).

## Anti-bias judge pairing

LLM-as-judge can exhibit self-preference. OpsBench avoids same-family judging, but cross-family pairing alone does not prove that bias has been controlled; the human-calibration step remains required.

The v0.2 run uses two cross-family judges. Anthropic outputs are judged by OpenAI; OpenAI and Google outputs are judged by Anthropic.

| SUT | Judge |
|---|---|
| Claude Opus 5 | GPT-5.6 Terra |
| Claude Sonnet 5 | GPT-5.6 Terra |
| GPT-5.6 Terra | Claude Sonnet 5 |
| Gemini 3.6 Flash | Claude Sonnet 5 |

## Why this exists

Foundation model benchmarks measure code, math, reasoning, and general knowledge. None of them measure the work an on-call engineer actually does at 3am: read a noisy alert, ignore the boilerplate, summarize what matters, suggest the next step.

Operational AI (AIOps copilots, SRE assistants, NOC agents) is shipping fast inside Datadog, PagerDuty, BigPanda, Splunk, Cisco. Every vendor claims AI quality. Nobody publishes their eval rubric. This is the rubric I wish existed when I started shipping AI features for on-call workflows.

## What this benchmark does NOT measure

- **Latency under load.** Reported latency is end-to-end API time from five sequential calls per model. It includes network and provider overhead and is not a concurrency, streaming, or load test.
- **Multi-turn dialogue.** Each scenario is one-shot summarization.
- **Tool use.** Models are not given tools (CMDB lookup, runbook retrieval, ticket creation). Adding tool use changes the task; planned for v0.3.
- **Real customer data.** Scenarios are synthetic and modeled after public incident reports. No PII or proprietary telemetry. This means the benchmark cannot distinguish a model that pattern-matches well on public incident vocabulary from a model that would handle a novel real-world payload.
- **A combined cost-quality score.** Cost and latency are reported separately; quality alone determines rank.

## Related work and inspiration

- [Hamel Husain on evals](https://hamel.dev/blog/posts/evals/), the core methodology this benchmark follows.
- [agentic-pm-workflow/evals/peer-review](https://github.com/sowsk/agentic-pm-workflow/tree/main/evals/peer-review), the eval suite this benchmark's runner and scorer were adapted from.
- [SWE-bench](https://www.swebench.com/), [MTEB](https://huggingface.co/spaces/mteb/leaderboard), [HumanEval](https://github.com/openai/human-eval), public benchmarks for adjacent capabilities. opsbench fills the operational gap none of them cover.

## Contributing

Two ways to help:

- **Add a scenario.** Fork, drop a JSON file in `scenarios/<category>/` matching [scenarios/SCHEMA.md](scenarios/SCHEMA.md), open a PR. Scenarios from your domain are more valuable than another network-outage example.
- **Run the benchmark and publish the result.** Open an issue with a link to your `runs/<timestamp>/` directory and a one-paragraph "what surprised me" note.

## Topics

Suggested GitHub repo topics (add via the GitHub UI under Settings then Topics, not via code):

`llm-eval` `aiops` `observability` `incident-response` `alert-fatigue` `on-call` `sre` `claude` `gpt-5` `gemini` `anthropic-evals` `openai-evals` `public-benchmark` `agenticops` `prompt-engineering` `eval-driven-development` `ops-ai` `monitoring`

## License

MIT.

## About

I'm [Sowmya Krishnamoorthy](https://www.linkedin.com/in/sowmya-krishnamoorthy), a product manager working on observability and AI for operations at ThousandEyes (Cisco). I'm interested in the gap between an AI feature that looks impressive in a demo and one an operator can actually trust during an incident.

I built opsbench to explore that gap in public: can a model separate signal from noise, stay grounded in the evidence, and suggest a useful next step when time matters? I'm especially interested in practical evals that reflect real operational work.

[@sowsk](https://github.com/sowsk) on GitHub.
