import unittest
from pathlib import Path

from src.validate_scenarios import SCENARIOS_DIR, validate_file


class ScenarioValidationTests(unittest.TestCase):
    def test_all_committed_scenarios_are_valid(self) -> None:
        errors: list[str] = []
        paths = sorted(Path(SCENARIOS_DIR).rglob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            errors.extend(validate_file(path))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
