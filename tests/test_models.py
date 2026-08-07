import unittest

from src.models import PRICING, family_of


class ModelCatalogTests(unittest.TestCase):
    def test_current_model_families(self) -> None:
        expected = {
            "claude-opus-5": "anthropic",
            "claude-sonnet-5": "anthropic",
            "gpt-5.6-sol": "openai",
            "gpt-5.6-terra": "openai",
            "gpt-5.6-luna": "openai",
            "gemini-3.6-flash": "google",
            "gemini-3.5-flash-lite": "google",
        }
        for model, family in expected.items():
            with self.subTest(model=model):
                self.assertEqual(family_of(model), family)
                self.assertIn(model, PRICING)


if __name__ == "__main__":
    unittest.main()
