# Methodology

How opsbench v0.1 scores models on alert summarization.

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

Did the model invent host names, IP addresses, service names, or timestamps not present in the input?

The runner extracts entities from the SUT output using simple regex:

- IPv4: `\b(?:\d{1,3}\.){3}\d{1,3}\b`
- Hostnames: `\b[a-z0-9-]+\.(?:com|net|internal|local|prod|stage|svc)[a-z0-9.-]*\b`
- ISO timestamps: `\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b`
- Allow-list match against the scenario's `entities` field.

If every extracted entity is in the allow-list, score = 2. If any is not, score = 0. No partial credit.

This dimension is binary on purpose. Hallucinating a host name in operational summaries is a hard fail.

## Aggregate score

Per (model, scenario): sum of the 5 dimension scores. Max = 10.

Per model: mean across all 25 scenarios, normalized to a 0-2 scale by dividing by 5. Reported in the leaderboard as the "Mean score" column.

## Anti-bias judge pairing

Each SUT is paired with a judge from a different model family to control for self-preference bias.

| SUT | Judge |
|---|---|
| Claude Sonnet 4.6 | GPT-5 |
| Claude Opus 4.8 | GPT-5 |
| GPT-5 | Claude Sonnet 4.6 |
| Gemini 2.5 Pro | Claude Sonnet 4.6 |

If a new judge model is introduced, all SUTs already judged by the prior judge must be re-judged with the new one and the leaderboard re-published with the methodology change called out in the run notes.

## Validation against human scoring

For the first published run, hand-score 3 cases (one per non-control category) and compare against the judge. Target agreement: 80 percent or better on the 4 judge-scored dimensions. If below 80 percent, the run is published with a warning and the judge prompt is revised before the next run.

Validation cases for v0.1:

- `network-outage-001-bgp-flap`
- `app-perf-regression-001-db-pool-exhaustion`
- `security-event-001-credential-spray`

## Known limitations of the methodology

- Synthetic scenarios pattern-match to public incident vocabulary. A model that has memorized incident.io post-mortems will look better than one that has not, even if real on-call performance is identical.
- The 2-sentence cap is a deliberate constraint. Models that summarize in 3-4 sentences may be more useful in production but score lower here.
- The judge sees the reference summary. There is some risk that the judge anchors on the reference even though instructed not to. Mitigated by anti-bias pairing and validation against human scoring.
- Hallucinated entities check uses regex, which misses entity types not in the regex set. v0.1 explicitly does not check, for example, error code numbers or version strings.

## Reproducibility

Every published run includes:

- Git commit hash of the runner.
- Exact model IDs and versions for SUT and judge.
- Full `outputs.jsonl` and `scores.jsonl`.
- Total tokens and cost.
- Any methodology changes since the previous published run, called out at the top of the run notes.

If a published number cannot be reproduced from the committed artifacts plus the methodology, that is a bug and should be filed as an issue.
