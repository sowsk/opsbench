import unittest
from pathlib import Path

from src.run_bench import REPO_ROOT, display_path, resolve_out_dir


class OutputPathTests(unittest.TestCase):
    def test_relative_out_dir_resolves_from_repo_root(self) -> None:
        self.assertEqual(
            resolve_out_dir("runs/openai-key-smoke", "unused"),
            REPO_ROOT / "runs/openai-key-smoke",
        )

    def test_repo_path_displays_as_relative(self) -> None:
        self.assertEqual(display_path(REPO_ROOT / "runs/test"), "runs/test")

    def test_external_absolute_path_is_supported(self) -> None:
        external = Path("/tmp/opsbench-test")
        self.assertEqual(resolve_out_dir(str(external), "unused"), external)
        self.assertEqual(display_path(external), str(external))


if __name__ == "__main__":
    unittest.main()
