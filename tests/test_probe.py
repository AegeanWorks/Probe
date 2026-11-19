"""Unit tests for probe's pure functions and checks (all local, fast)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import probe


class DigestTest(unittest.TestCase):
    def test_body_digest_of_empty_is_the_well_known_vector(self):
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(probe.body_digest(b""), expected)

    def test_body_digest_changes_with_content(self):
        self.assertNotEqual(probe.body_digest(b"a"), probe.body_digest(b"b"))


class CheckResultTest(unittest.TestCase):
    def test_as_dict_records_all_fields(self):
        entry = probe.CheckResult("fs", True, "wrote+read back 42 bytes", 1.25).as_dict()
        self.assertEqual(entry, {"name": "fs", "passed": True,
                                 "evidence": "wrote+read back 42 bytes", "ms": 1.25,
                                 "error": None})


class ImportsScanTest(unittest.TestCase):
    def _write(self, root: Path, name: str, text: str) -> None:
        (root / name).write_text(text, encoding="utf-8")

    def test_stdlib_and_local_imports_are_not_third_party(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "local_a.py", "import json\nfrom pathlib import Path\n")
            self._write(root, "local_b.py", "import local_a\n")
            third, unparseable = probe.imports_scan(root)
        self.assertEqual(third, [])
        self.assertEqual(unparseable, [])

    def test_flags_a_third_party_import_by_name(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "a.py", "import definitely_not_stdlib_xyz123\n")
            third, unparseable = probe.imports_scan(root)
        self.assertEqual(third, ["definitely_not_stdlib_xyz123"])
        self.assertEqual(unparseable, [])

    def test_records_unparseable_files_without_raising(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, "a.py", "def broken(:\n")
            third, unparseable = probe.imports_scan(root)
        self.assertEqual(third, [])
        self.assertEqual(unparseable, ["a.py"])


class FsCheckTest(unittest.TestCase):
    def test_roundtrip_passes_and_cleans_up(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = probe.run_fs_check(root)
            self.assertTrue(result.passed, result.evidence)
            self.assertIn("wrote+read back", result.evidence)
            self.assertFalse((root / "reports" / probe.ROUNDTRIP_NAME).exists())


class BuildReportTest(unittest.TestCase):
    def test_report_counts_and_preserves_check_order(self):
        with TemporaryDirectory() as tmp:
            report = probe.build_report(Path(tmp), [
                probe.CheckResult("fs", True, "a", 1.0),
                probe.CheckResult("shell", False, "b", 2.0, "boom"),
            ], deep=True)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["total"], 2)
        self.assertEqual([entry["name"] for entry in report["checks"]], ["fs", "shell"])
        self.assertTrue(report["deep"])
        self.assertIn("T", report["generated_at"])

    def test_write_report_round_trips_through_json(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = probe.build_report(root, [probe.CheckResult("fs", True, "wrote 42 bytes", 1.25)],
                                        deep=False)
            target = probe.write_report(root, report, out=str(root / "report.json"))
            data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(data["checks"][0]["evidence"], "wrote 42 bytes")
        self.assertEqual(data["passed"], 1)


if __name__ == "__main__":
    unittest.main()
