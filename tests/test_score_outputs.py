import unittest
from pathlib import Path

from src.score_outputs import display_path, extract_entities, has_valid_judge_scores, sentence_count


class EntityExtractionTests(unittest.TestCase):
    def test_abbreviations_are_not_hostnames(self) -> None:
        entities = extract_entities("Check the queue, e.g. retry depth, i.e. the live backlog.")
        self.assertEqual(entities["hostnames"], [])

    def test_real_hostnames_are_preserved(self) -> None:
        entities = extract_entities("Inspect edge-rtr-01.sfo.prod and wiki.internal.")
        self.assertEqual(entities["hostnames"], ["edge-rtr-01.sfo.prod", "wiki.internal"])

    def test_ipv4_and_decimals_are_not_hostnames(self) -> None:
        entities = extract_entities("Neighbor 198.51.100.1 shifted 12.4 Gbps.")
        self.assertEqual(entities["ips"], ["198.51.100.1"])
        self.assertEqual(entities["hostnames"], [])

    def test_extracted_entities_are_deterministic(self) -> None:
        entities = extract_entities("Check z.internal, then a.internal, then z.internal.")
        self.assertEqual(entities["hostnames"], ["z.internal", "a.internal", "z.internal"])


class SentenceCountTests(unittest.TestCase):
    def test_common_abbreviations_do_not_add_sentences(self) -> None:
        self.assertEqual(sentence_count("Check the queue, e.g. retry depth. Then page the owner."), 2)


class JudgeResultTests(unittest.TestCase):
    def test_only_complete_successful_judge_results_are_reusable(self) -> None:
        valid = {"judge_scores": {"scores": {"factual_accuracy": 2}}, "judge_error": None}
        malformed = {"judge_scores": None, "judge_error": "JSONDecodeError"}

        self.assertTrue(has_valid_judge_scores(valid))
        self.assertFalse(has_valid_judge_scores(malformed))
        self.assertFalse(has_valid_judge_scores(None))


class OutputPathTests(unittest.TestCase):
    def test_external_absolute_path_is_supported(self) -> None:
        self.assertEqual(display_path(Path("/tmp/opsbench-run")), "/tmp/opsbench-run")


if __name__ == "__main__":
    unittest.main()
