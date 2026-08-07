# Methodology

How OpsBench v0.2 scores models on alert summarization and reports observed API latency and estimated cost.

## Task

The system under test (SUT) receives:

1. A **system prompt** that defines the role (operations summarization assistant) and the output format (exactly 2 sentences).
2. A **user message** with the raw alert payload and 5 minutes of preceding context lines.

The SUT returns free-form text. The runner stores it verbatim. No post-processing.

## Scoring

Each output is scored on 5 dimensions. Four are LLM-as-judge scored 0 to 2. One is automated.

### 1. Factual accuracy (judge, 0 to 2)

Does the summary correctly describe what the alert said?

- **2:** Every factual claim in the summary is supported by the raw alert or context lines.
- **1:** One minor factual error, or one detail mis-attributed (right concept, wrong source).
- **0:** A material factual error that would mislead an on-call engineer.

The judge is shown the SUT's output and the scenario's `reference_summary`, but explicitly told that the reference is one valid summary, not the only valid summary. The grade is "is the SUT factually consistent with the source," not "does it match the reference word for word."

### 2. Signal-to-noise (judge, 0 to 2)

Did the model skip the boilerplate and surface what matters?

- **2:** Summary leads with the highest-priority signal in the payload. Ignores irrelevant context.
- **1:** Mentions the right signal but buries it, or wastes a sentence on low-value context.
- **0:** Leads with boilerplate, repeats the alert title, or summarizes the wrong thing.

The judge has access to a `noise_lines` field in the scenario marking which context lines are deliberately irrelevant. Penalize summaries that quote those lines.

### 3. Action orientation (judge, 0 to 2)

Does the summary suggest a defensible next step?

- **2:** Names a specific next action or investigation path tied to the alert's signal (for example, "check upstream BGP neighbor status on R3" rather than "investigate").
- **1:** Suggests an action but in generic terms.
- **0:** No action suggested, or suggests an action contradicted by the payload.

A defensible action does not have to be the right action. The benchmark cannot determine that without ground truth from the real incident. It only checks that the model produced one, that the action is specific, and that it is consistent with what the payload says.

### 4. Brevity (judge, 0 to 2)

Did the summary stay at or under the 2-sentence cap?

- **2:** Exactly 1 or 2 sentences, no headers, no bullets, no preamble.
- **1:** 3 sentences, or 2 sentences with light formatting noise (a colon-introduced list).
- **0:** 4+ sentences, multi-paragraph, or includes bullet points.

Sentence counting uses period, question mark, and exclamation mark boundaries with abbreviation exclusions. The judge confirms by reading.

### 5. No hallucinated entities (automated, 0 or 2)

Did the model invent host names, IP addresses, or timestamps not present in the input?

The runner extracts entities from the SUT output using simple regex:

- IPv4: `\b(?:\d{1,3}\.){3}\d{1,3}\b`
- Hostnames: final segment must begin with a letter and contain at least two characters; this excludes IPs, decimals, and abbreviations such as `e.g.`.
- ISO timestamps: supports `Z` and numeric timezone suffixes.
- Allow-list match against the scenario's `entities` field.

If every extracted entity is in the allow-list, score = 2. If any is not, score = 0. No partial credit.

This dimension is binary on purpose. Hallucinating a host name in operational summaries is a hard fail.

## Aggregate score

Per (model, scenario): sum of the 5 dimension scores. Max = 10.

Per model: mean across all five v0.2 scenarios, normalized to a 0-2 scale by dividing by 5. Reported in the leaderboard as the "Mean quality" column.

Quality alone determines leaderboard rank. Cost and latency are deliberately not folded into the quality score.

## Operational measurements

The runner records end-to-end elapsed time, input tokens, output tokens, and estimated API cost for every successful call. The leaderboard reports:

- **Median observed latency:** median elapsed time across the five sequential scenario calls. This includes client, network, queueing, provider, and generation time; it is not isolated server-side inference latency.
- **Average cost per scenario:** mean estimated cost across the five calls, using the token counts returned by each provider and the pricing snapshot in `src/models.py`.

These measurements are directional. Five sequential calls are enough to expose large product-level differences, but not enough to characterize tail latency, throughput, caching, or performance under load.

## Anti-bias judge pairing

Each SUT is paired with a judge from a different model family to avoid same-family judging. This reduces one obvious source of self-preference, but it is not sufficient evidence that judge bias is controlled.

The v0.2 run uses current Anthropic, OpenAI, and Google models. Every published run records its exact SUT and judge IDs.

| SUT | Judge |
|---|---|
| Claude Opus 5 | GPT-5.6 Terra |
| Claude Sonnet 5 | GPT-5.6 Terra |
| GPT-5.6 Terra | Claude Sonnet 5 |
| Gemini 3.6 Flash | Claude Sonnet 5 |

If a new judge model is introduced, all SUTs already judged by the prior judge must be re-judged with the new one and the leaderboard re-published with the methodology change called out in the run notes.

## Validation against human scoring

The v0.2 judge has not yet been calibrated against author scoring. Until this is complete, the leaderboard must remain labeled as a pilot rather than a validated model ranking.

The project author should hand-score all four models on the three cases below and compare the 48 resulting dimension scores against the judge. Target exact agreement: 80 percent or better. If agreement is below 80 percent, keep the warning and revise the judge prompt before the next run. The worksheet and procedure live under `validation/`.

Validation cases for v0.2:

- `network-outage-001-bgp-flap`
- `app-perf-regression-001-gke-slo-cloudsql-replica-lag`
- `security-event-001-cloud-armor-waf-checkout-block`

## Known limitations of the methodology

- Synthetic scenarios pattern-match to public incident vocabulary. A model that has memorized incident.io post-mortems will look better than one that has not, even if real on-call performance is identical.
- The 2-sentence cap is a deliberate constraint. Models that summarize in 3-4 sentences may be more useful in production but score lower here.
- The judge sees the reference summary. There is some risk that the judge anchors on it even though instructed not to. Cross-family pairing does not remove this risk, and author calibration is still pending.
- Hallucinated entities check uses regex, which misses entity types not in the regex set. v0.2 explicitly does not check, for example, error code numbers or version strings.
- Observed latency uses five sequential calls per model from one client location. It is not a statistically stable provider performance comparison.

## Reproducibility

Every published run directory under `runs/published/` includes:

- Git commit hash of the runner.
- Exact model IDs and versions for SUT and judge.
- Full `outputs.jsonl` and `scores.jsonl`.
- Per-call tokens, observed latency, and estimated cost, plus aggregate latency and cost.
- Any methodology changes since the previous published run, called out at the top of the run notes.

If a published number cannot be reproduced from the committed artifacts plus the methodology, that is a bug and should be filed as an issue.
