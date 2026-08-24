import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class ReleaseTests(unittest.TestCase):
    def test_support_addresses(self):
        text = (ROOT / "SUPPORT.md").read_text()
        for value in ("bc1qh474jpyw4malh0fmg2uy7n05ggtjvnjtcwhdne",
                      "0x8fcC9C0d1FFCE17b1dEC91B299E56d66BC126Ba8",
                      "D6qp2awRAHVo2VgincTAW5frhnJ9MBZcz4"):
            self.assertEqual(text.count(value), 1)
        self.assertIn("do not purchase support, ownership, returns", text)

    def test_private_marker_absent(self):
        marker = "World" + "Forge"
        for path in ROOT.rglob("*"):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts and path.name != "LICENSE":
                self.assertNotIn(marker, path.read_text(errors="ignore"), str(path))

    def test_zero_dependency_demo(self):
        self.assertIn("dependencies = []", (ROOT / "pyproject.toml").read_text())
        result = subprocess.run([sys.executable, "-m", "orderflowsage", "demo"], cwd=ROOT,
                                text=True, capture_output=True, check=True)
        self.assertIn("not_a_prediction_or_signal", result.stdout)


if __name__ == "__main__":
    unittest.main()
