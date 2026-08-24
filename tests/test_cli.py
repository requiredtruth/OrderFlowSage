import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "orderflowsage/data/demo_config.json"
EVENTS = ROOT / "orderflowsage/data/demo.jsonl"


class CliTests(unittest.TestCase):
    def invoke(self, *args, check=True):
        return subprocess.run([sys.executable, "-m", "orderflowsage", *map(str, args)], cwd=ROOT,
                              text=True, capture_output=True, check=check)

    def test_demo_is_plain_and_deterministic(self):
        first, second = self.invoke("demo").stdout, self.invoke("demo").stdout
        self.assertEqual(first, second)
        self.assertIn("not_a_prediction_or_signal", first)
        self.assertNotIn("\x1b", first)

    def test_run_verify_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            self.invoke("run", CONFIG, EVENTS, report)
            self.assertEqual(self.invoke("verify", CONFIG, EVENTS, report).stdout, "report verified\n")
            self.assertIn("integrity=complete_sequence", self.invoke("summary", report).stdout)

    def test_missing_file_has_no_traceback(self):
        result = self.invoke("run", CONFIG, "missing.jsonl", "out.json", check=False)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
