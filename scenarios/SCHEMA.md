# Scenario schema

Every scenario is a single JSON file under `scenarios/<category>/<NNN-slug>.json`. Categories: `network-outage`, `compute-fabric`, `app-perf-regression`, `security-event`, `capacity-warning`.

## Category definitions

- **network-outage**: connectivity issues at the IP/Ethernet/InfiniBand layers across nodes (BGP, MPLS, routing, link flaps, transit provider issues). Scenarios test the SUT's ability to reason about cross-node network failure and impact.
- **compute-fabric**: GPU/AI cluster interconnect issues (NVLink, NVSwitch, PCIe at the GPU layer, RoCE/InfiniBand at the GPU layer). Scenarios test the SUT's ability to reason about AI compute fabric degradation distinct from traditional networking. The on-call who'd get paged is GPU/compute platform, not network.
- **app-perf-regression**: application-level performance issues (database slowness, API latency, memory leaks, queue depth growth) not rooted in fabric or hardware degradation.
- **security-event**: authentication anomalies, intrusion indicators, exfiltration patterns, privilege escalations.
- **capacity-warning**: resource limits being approached (disk filling, memory pressure, queue saturation, quota exhaustion).

## Required fields

```json
{
  "id": "network-outage-001-bgp-flap",
  "category": "network-outage",
  "title": "Short human-readable title (one line).",
  "severity": "critical | high | medium | low",
  "alert": "The raw alert payload as it would arrive in the on-call tool. Multi-line string.",
  "context": [
    "Context line 1 (timestamp + log/metric/event)",
    "Context line 2",
    "..."
  ],
  "noise_lines": [0, 3, 5],
  "entities": {
    "hostnames": ["edge-rtr-01.sfo.prod"],
    "ips": ["10.42.0.1", "2001:db8::1"],
    "services": ["bgp", "ospf"],
    "timestamps": ["2026-06-07T14:23:00"]
  },
  "reference_summary": "One author-written 2-sentence summary that meets the rubric. Used by the judge as one valid answer, not the only valid answer.",
  "reference_action": "One author-written defensible next step. Used by the judge to calibrate action orientation."
}
```

## Field notes

- **`id`**: must equal `<category>-<NNN>-<slug>`, where `NNN` is a zero-padded 3-digit number unique within the category.
- **`alert`**: realistic format for the source tool (Prometheus, Datadog, PagerDuty, ThousandEyes-style, etc.). Variety across scenarios is good; do not standardize.
- **`context`**: 5 to 15 lines of preceding log lines, metric values, change-management events, or related alerts. Mix relevant signal with deliberate noise.
- **`noise_lines`**: zero-indexed positions in `context` that the SUT should ignore. The judge penalizes summaries that quote noise lines. At least 1 noise line per scenario; recommended 2 to 4.
- **`entities`**: the allow-list for the automated hallucination check. Every entity that appears in `alert` or `context` must be listed here, including hostnames embedded inside URLs (e.g. if the alert mentions `https://wiki.internal/runbooks/foo`, include `wiki.internal` in `hostnames`). Anything the SUT outputs that is not in this list is flagged as hallucinated.
- **`reference_summary`**: write this yourself, as a senior PM with operational instincts. The judge anchors lightly on it but is told it is one valid answer, not the only one.
- **`reference_action`**: a specific defensible next step that an on-call engineer would actually take. Not "investigate further"; something like "check BGP neighbor table on edge-rtr-01".

## How to add a scenario

1. Pick a category folder.
2. Find the next available 3-digit number.
3. Copy an existing scenario as a template.
4. Edit. Be honest about whether the scenario reflects a real-world alert shape; if it does not, fix the shape, not the alert text.
5. Run `python -m src.validate_scenarios` (TODO post-v0.1) before opening a PR.

## Diversity targets for v0.1

Across 25 to 30 scenarios:

- At least 3 scenarios per category, evenly weighted toward 5 to 6.
- At least 1 scenario per category should be deliberately ambiguous (no clear single right action) to stress action orientation.
- At least 2 scenarios should contain a red herring (a context line that points toward a plausible-but-wrong root cause) to stress factual accuracy.
- No two scenarios should share the same root cause.
