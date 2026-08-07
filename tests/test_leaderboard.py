import unittest

from src.leaderboard import build_table


class LeaderboardTests(unittest.TestCase):
    def test_published_artifact_path_and_note_are_rendered(self) -> None:
        summary = {
            "model-a": {
                "mean_score": 2.0,
                "judge_failures": 0,
                "dimension_means": {
                    "factual_accuracy": 2.0,
                    "signal_to_noise": 2.0,
                    "action_orientation": 2.0,
                    "brevity": 2.0,
                    "no_hallucinated_entities": 2.0,
                },
                "performance": {
                    "median_observed_latency_ms": 1250,
                    "mean_cost_usd_per_scenario": 0.003456,
                },
            }
        }
        rendered = build_table(summary, "run-1", "runs/published/run-1", "pilot")
        self.assertIn("`runs/published/run-1`", rendered)
        self.assertIn("> Run note: pilot", rendered)
        self.assertIn("1.25s", rendered)
        self.assertIn("$0.0035", rendered)


if __name__ == "__main__":
    unittest.main()
