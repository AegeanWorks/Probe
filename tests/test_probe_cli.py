"""Integ tests: the probe CLI runs the battery end-to-end in the project root."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent


class RunCliTest(unittest.TestCase):
    def _run(self, *args, timeout=60.0):
        return subprocess.run(
            [sys.executable, str(ROOT / "probe.py"), "run", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT))

    def test_default_battery_passes_and_report_round_trips(self):
        with TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "report.json")
            proc = self._run("--out", out)
            report = json.loads(Path(out).read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual([entry["name"] for entry in report["checks"]],
                         ["fs", "shell", "git", "imports"])
        self.assertEqual(report["passed"], report["total"])
        self.assertTrue(all(entry["passed"] for entry in report["checks"]))

    def test_deep_battery_adds_timing_and_web_checks(self):
        with TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "report-deep.json")
            self._run("--deep", "--out", out)
            report = json.loads(Path(out).read_text(encoding="utf-8"))
        names = [entry["name"] for entry in report["checks"]]
        self.assertEqual(names, ["fs", "shell", "git", "imports", "timing", "web"])
        timing = next(entry for entry in report["checks"] if entry["name"] == "timing")
        self.assertTrue(timing["passed"], timing["evidence"])


if __name__ == "__main__":
    unittest.main()
