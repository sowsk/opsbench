# opsbench

A public benchmark for how well LLMs summarize and reason about operational alerts. Run by a PM who is tired of vendor demos that test only the easy cases.

v0.1 scores one task: **alert summarization**. Given a raw observability alert plus 5 minutes of preceding context, can a frontier LLM produce a 2-sentence summary that is factually accurate, action-oriented, and does not invent things that were not in the input?

Three things make opsbench different from the AIOps benchmarks vendors publish in their own white papers:

1. The scoring rubric is public, versioned, and named (factual accuracy, signal-to-noise, action orientation, brevity, no hallucinated entities).
2. Each model under test is judged by a model from a different family, so Claude is not grading itself.
3. The "what this does NOT measure" section is the longest in this README on purpose.

## What "good" looks like

Before installing anything, here is one of the 25 v0.1 scenarios.

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

Full scenario format and the other 24: [scenarios/SCHEMA.md](scenarios/SCHEMA.md).

## Use this if...

- **You are picking a model for an incident copilot or alert summarizer.** Open the leaderboard, sort by the dimensions you care about (factual accuracy if your concern is trust, brevity if you have a UI constraint), and stop relying on vendor blog posts.
- **You are about to ship an AI alerting feature.** Run your candidate prompt and model against the suite before you put it in front of an SRE. Failing on opsbench means failing in production, only louder.
- **You are evaluating an AIOps vendor.** Ask them to publish their numbers against this benchmark. If they refuse, that is the answer.
- **You are a PM or engineer building eval suites for ops AI.** Use this as a worked example: 5-dimension rubric, anti-bias judge pairing, automated plus LLM-as-judge split, validation against human scoring. Fork and adapt.
- **You are an SRE skeptical of "AI for on-call" claims.** Run the suite yourself in 10 minutes for $2. Then form an opinion.

## Leaderboard

<!-- LEADERBOARD:START -->
*v0.1 has not been run yet. Once the first run lands, this block updates in place via `python -m src.leaderboard --run-dir runs/<timestamp>`. Do not edit by hand.*

Shape of what will appear here once v0.1 publishes:

| Rank | Model (SUT) | Judge | Mean (0-2) | Factual | Signal/noise | Action | Brevity | No hallucination |
|---|---|---|---|---|---|---|---|---|
| 1 | claude-opus-4-8 | gemini-2.5-pro | TBD | TBD | TBD | TBD | TBD | TBD |
| 2 | claude-sonnet-4-6 | gemini-2.5-pro | TBD | TBD | TBD | TBD | TBD | TBD |
| 3 | gemini-2.5-pro | claude-sonnet-4-6 | TBD | TBD | TBD | TBD | TBD | TBD |

GPT-5 and Haiku 4.5 join the table in v0.2 once a personal OpenAI key is wired in. The runner, scorer, and pricing tables already support them.
<!-- LEADERBOARD:END -->

## How it works

1. **Scenarios** in `scenarios/` are 25 synthetic alert payloads across 4 categories (network outage, app perf regression, security event, capacity warning). Each JSON file has the raw alert, 5 minutes of preceding context, a ground-truth entity set, and a reference summary. See [scenarios/SCHEMA.md](scenarios/SCHEMA.md).
2. **Runner** (`src/run_bench.py`) sends each scenario to each model in `--models`, writes one row per (scenario, model) to `runs/<timestamp>/outputs.jsonl`.
3. **Scorer** (`src/score_outputs.py`) runs two passes per output. Pass 1 is automated (hallucinated-entity check via regex, brevity check). Pass 2 is LLM-as-judge with anti-bias pairing: every model under test is judged by a model from a different family.
4. **Leaderboard** (`src/leaderboard.py`) aggregates `scores.jsonl` into a markdown table and updates this README in place.

Full rubric, validation plan, and known methodology limitations: [methodology.md](methodology.md).

## Install

| Path | Command | Status |
|---|---|---|
| pip (when packaged) | `pip install opsbench` | Coming v0.2 |
| uvx (zero-install run) | `uvx opsbench run --models claude-opus-4-8,gemini-2.5-pro` | Coming v0.2 |
| Clone and venv | see below | Works today |

```bash
git clone https://github.com/sowsk/opsbench.git
cd opsbench
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in ANTHROPIC_API_KEY and GEMINI_API_KEY (OPENAI_API_KEY is v0.2)

python -m src.run_bench --models claude-sonnet-4-6,claude-opus-4-8,gemini-2.5-pro
python -m src.score_outputs --run-dir runs/<timestamp>
python -m src.leaderboard --run-dir runs/<timestamp>
```

## Bring your own keys

You bring one API key per provider you want to test. Costs are per-provider, no opsbench markup.

| Provider | Env var | Estimated cost, full 25-scenario run | Per-million-token pricing (June 2026) |
|---|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | ~$0.90 Opus 4.8 SUT + ~$0.40 Sonnet 4.6 judge | $5 in / $25 out (Opus), $3 in / $15 out (Sonnet) |
| Google | `GEMINI_API_KEY` | ~$0.60 Gemini 2.5 Pro (SUT + judge) | $3.50 in / $14 out |
| OpenAI (v0.2) | `OPENAI_API_KEY` | ~$0.90 GPT-5 SUT | $5 in / $25 out |

A full v0.1 run (25 scenarios x 3 SUT models x 1 judge call each) costs roughly $1.50 to $3 and finishes in 6 to 10 minutes. Pricing snapshot is in [src/models.py](src/models.py); update there when providers change.

## Anti-bias judge pairing

LLM-as-judge has a well-known self-preference bias: a model judging its own output scores it higher than another model would. opsbench controls for this by pairing each system-under-test (SUT) with a judge from a different model family.

v0.1 ships a two-family scheme (Anthropic + Google). v0.2 adds OpenAI once a personal API key is available.

| SUT | Judge |
|---|---|
| Claude Sonnet 4.6 | Gemini 2.5 Pro |
| Claude Opus 4.8 | Gemini 2.5 Pro |
| Gemini 2.5 Pro | Claude Sonnet 4.6 |

## Why this exists

Foundation model benchmarks measure code, math, reasoning, and general knowledge. None of them measure the work an on-call engineer actually does at 3am: read a noisy alert, ignore the boilerplate, summarize what matters, suggest the next step.

Operational AI (AIOps copilots, SRE assistants, NOC agents) is shipping fast inside Datadog, PagerDuty, BigPanda, Splunk, Cisco. Every vendor claims AI quality. Nobody publishes their eval rubric. This is the rubric I wish existed when I started shipping AI features for on-call workflows.

## What this benchmark does NOT measure

- **Latency under load.** Single-call benchmark, no concurrency or streaming test.
- **Multi-turn dialogue.** Each scenario is one-shot summarization.
- **Tool use.** Models are not given tools (CMDB lookup, runbook retrieval, ticket creation). Adding tool use changes the task; planned for v0.3.
- **Real customer data.** Scenarios are synthetic and modeled after public incident reports. No PII or proprietary telemetry. This means the benchmark cannot distinguish a model that pattern-matches well on public incident vocabulary from a model that would handle a novel real-world payload.
- **Cost-quality tradeoff.** Reported tokens and cost are informational; the ranking does not penalize expensive models.
- **GPT-5 and OpenAI models in v0.1.** The runner, scorer, and pricing tables already support them; GPT-5 joins the leaderboard in v0.2.

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

Built by [Sowmya Krishnamoorthy](https://www.linkedin.com/in/sowmya-krishnamoorthy), senior PM at ThousandEyes (Cisco). I own the alerts, integrations, and dashboards platforms, and the AI / agentic strategy across them. I shipped Adaptive Alert Detection (77 percent fewer flapping alerts across 826 production orgs) and built an internal Claude-powered alert optimization tool. Real alert summarization is harder than benchmarks suggest. opsbench is my attempt to put a public number on it.

[@sowsk](https://github.com/sowsk) on GitHub.
