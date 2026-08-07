# Human calibration

Status: **pending author scoring**.

The v0.2 leaderboard uses cross-family LLM judges, but cross-family pairing is a design choice, not proof that judge bias has been controlled. Before presenting the leaderboard as validated, the project author should independently score the selected outputs in `human-scoring.csv` without looking at the judge scores, then calculate exact agreement across the four judge-scored dimensions.

## Procedure

1. Open `runs/published/2026-08-07_v0.2/outputs.jsonl` and locate each scenario/model pair listed in `human-scoring.csv`.
2. Score factual accuracy, signal-to-noise, action orientation, and brevity from 0 to 2 using `methodology.md`.
3. Fill only the `human_*` columns. Do not inspect `scores.jsonl` first.
4. Compare the 48 human dimension scores with the corresponding judge scores.
5. Report exact agreement and within-one agreement. The original 80% target applies to exact agreement.
6. If exact agreement is below 80%, keep the leaderboard labeled unvalidated and revise the judge prompt before the next run.

The three validation scenarios are real IDs in v0.2 and cover network, application, and security cases.
