#!/usr/bin/env python3
"""probe.py - a local-first capability probe for the agent workspace.

Runs an inspectable battery of falsifiable environment checks and writes a
verifiable JSON report of what was actually measured. Every check returns a
CheckResult whose evidence names what was observed; a report claims a check
passed only when the observation supports it.

Checks:

    fs       filesystem round-trip: write a file, read it back, delete it
    shell    python --version through sys.executable (argv list, 10 s timeout)
    git      is the tree inside a git work tree?
    imports  scan project .py files for imports outside stdlib and the project
    timing   wall time of `python -c pass` (deep only)
    web      fetch a URL and record status, size and body digest (deep only)

Usage:

    python probe.py run [--deep] [--url URL] [--json] [--out FILE]
    python probe.py checks

Exit codes: 0 when every check passed, 1 when any failed, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
REPORT_DIR_NAME = "reports"
ROUNDTRIP_NAME = ".fs-roundtrip.txt"
SHELL_TIMEOUT_S = 10.0
TIMING_BUDGET_MS = 1000.0
WEB_TIMEOUT_S = 10.0
DEFAULT_WEB_URL = "https://github.com/aegeanworks"

CHECK_DESCRIPTIONS = {
    "fs": "filesystem round-trip: write, read back and delete a file",
    "shell": "python --version via sys.executable (argv list, 10 s timeout)",
    "git": "is the tree inside a git work tree?",
    "imports": "scan project .py files for imports outside stdlib and the project",
    "timing": f"wall time of `python -c pass` vs {TIMING_BUDGET_MS:.0f} ms budget (deep)",
    "web": f"fetch {DEFAULT_WEB_URL} and record status, size and body digest (deep)",
}


@dataclass
class CheckResult:
    """One falsifiable measurement: what passed, the evidence observed, the cost in ms."""

    name: str
    passed: bool
    evidence: str
    ms: float
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        """The JSON-ready record of this check."""
        return {"name": self.name, "passed": self.passed, "evidence": self.evidence,
                "ms": self.ms, "error": self.error}


def _elapsed_ms(started: float) -> float:
    """Milliseconds since `started`, rounded to a clean value."""
    return round((time.perf_counter() - started) * 1000.0, 3)


def _short(text: str, limit: int = 120) -> str:
    """One line, truncated to `limit` characters, for evidence text."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def _subprocess(argv: Sequence[str], cwd: Optional[Path] = None,
                timeout: float = 10.0) -> Tuple[int, str, str]:
    """Run one argv as a list (never a shell string) and return (exit, out, err)."""
    proc = subprocess.run(list(argv), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


def run_fs_check(root: Path) -> CheckResult:
    """Round-trip a file in the project tree: write it, read it back, delete it."""
    started = time.perf_counter()
    report_dir = root / REPORT_DIR_NAME
    probe_path = report_dir / ROUNDTRIP_NAME
    payload = f"probe-fs-roundtrip {time.time():.6f}\n".encode("utf-8")
    passed = False
    evidence = "nothing written"
    error: Optional[str] = None
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        probe_path.write_bytes(payload)
        read_back = probe_path.read_bytes()
        if read_back == payload and len(read_back) > 0:
            passed = True
            evidence = f"wrote+read back {len(read_back)} bytes"
        else:
            evidence = f"read-back mismatch: wrote {len(payload)}, read {len(read_back)}"
            error = "read-back mismatch"
    except OSError as exc:
        evidence = f"write or read failed: {type(exc).__name__}: {exc}"
        error = f"{type(exc).__name__}: {exc}"
    if probe_path.exists():
        try:
            probe_path.unlink()
        except OSError as exc:
            error = f"cleanup: {type(exc).__name__}: {exc}"
    return CheckResult("fs", passed, evidence, _elapsed_ms(started), error)


def run_shell_check() -> CheckResult:
    """`python --version` through sys.executable (argv list, 10 s timeout)."""
    started = time.perf_counter()
    try:
        returncode, out, err = _subprocess([sys.executable, "--version"], timeout=SHELL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return CheckResult("shell", False, "python --version timed out", _elapsed_ms(started),
                           "timeout")
    except OSError as exc:
        return CheckResult("shell", False, f"could not start: {exc}", _elapsed_ms(started),
                           str(exc))
    text = (out + err).strip()
    passed = returncode == 0 and "Python" in text
    return CheckResult("shell", passed, text or f"exit {returncode}", _elapsed_ms(started),
                       None if passed else f"exit {returncode}")


def run_git_check(root: Path) -> CheckResult:
    """Is the tree inside a git work tree? (`git rev-parse --is-inside-work-tree`.)"""
    started = time.perf_counter()
    try:
        returncode, out, err = _subprocess(["git", "rev-parse", "--is-inside-work-tree"],
                                           cwd=root, timeout=SHELL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return CheckResult("git", False, "git rev-parse timed out", _elapsed_ms(started), "timeout")
    except OSError as exc:
        return CheckResult("git", False, f"git not runnable: {exc}", _elapsed_ms(started),
                           str(exc))
    text = out.strip() or err.strip()
    passed = returncode == 0 and text == "true"
    return CheckResult("git", passed, text or f"exit {returncode}", _elapsed_ms(started),
                       None if passed else f"exit {returncode}")


def _iter_project_files(root: Path) -> List[Path]:
    """All .py files in the project tree, sorted (excluding .git internals)."""
    return sorted(path for path in root.rglob("*.py") if ".git" not in path.parts)


def imports_scan(root: Path) -> Tuple[List[str], List[str]]:
    """Third-party imports across the project's .py files, plus the unparseable ones.

    An import is third-party when it is neither a stdlib module
    (``sys.stdlib_module_names``) nor a module of this project (a .py stem or a
    package directory with ``__init__.py``). Relative imports (level > 0) are
    local, so they are never third-party.
    """
    files = _iter_project_files(root)
    local = {path.stem for path in files} | {
        entry.name for entry in root.iterdir()
        if entry.is_dir() and (entry / "__init__.py").exists()
    }
    third_party: List[str] = []
    unparseable: List[str] = []
    for path in files:
        try:
            tree = ast.parse(path.read_bytes(), filename=str(path))
        except (SyntaxError, ValueError):
            unparseable.append(path.name)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    third_party.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    third_party.append(node.module.split(".")[0])
    stdlib = sys.stdlib_module_names
    third = sorted({name for name in third_party if name not in stdlib and name not in local})
    return third, unparseable


def run_imports_check(root: Path) -> CheckResult:
    """No third-party imports anywhere in the project tree (AST only)."""
    started = time.perf_counter()
    third, unparseable = imports_scan(root)
    parts = []
    if third:
        parts.append("third-party imports: " + ", ".join(third))
    if unparseable:
        parts.append("unparseable files: " + ", ".join(unparseable))
    evidence = "; ".join(parts) if parts else "all imports are stdlib or local"
    return CheckResult("imports", not third, evidence, _elapsed_ms(started),
                       "third-party imports present" if third else None)


def run_timing_check() -> CheckResult:
    """Wall time of `python -c pass` against TIMING_BUDGET_MS."""
    started = time.perf_counter()
    try:
        returncode, _out, _err = _subprocess([sys.executable, "-c", "pass"],
                                             timeout=SHELL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return CheckResult("timing", False, "python -c pass timed out", _elapsed_ms(started),
                           "timeout")
    except OSError as exc:
        return CheckResult("timing", False, f"could not start: {exc}", _elapsed_ms(started),
                           str(exc))
    elapsed = _elapsed_ms(started)
    passed = returncode == 0 and elapsed <= TIMING_BUDGET_MS
    evidence = f"python -c pass exit {returncode} in {elapsed:.1f} ms"
    return CheckResult("timing", passed, evidence, elapsed,
                       None if passed else f"exit {returncode}, budget {TIMING_BUDGET_MS:.0f} ms")


def body_digest(data: bytes) -> str:
    """The SHA-256 digest of the web response body, recorded as evidence."""
    return hashlib.sha256(data).hexdigest()


def run_web_check(url: str) -> CheckResult:
    """GET `url`; record the status, body size and digest of the response."""
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "probe/1"})
    try:
        with urllib.request.urlopen(request, timeout=WEB_TIMEOUT_S) as response:
            body = response.read()
            status = int(response.getcode() or 0)
    except (OSError, ValueError) as exc:
        return CheckResult("web", False, f"fetch failed: {_short(str(exc))}",
                           _elapsed_ms(started), _short(str(exc)))
    digest = body_digest(body)
    passed = 200 <= status < 400
    evidence = f"GET {url}: HTTP {status}, {len(body)} bytes, sha256:{digest}"
    return CheckResult("web", passed, evidence, _elapsed_ms(started),
                       None if passed else f"HTTP {status}")


def run_battery(root: Path, deep: bool, url: str) -> List[CheckResult]:
    """The default battery (fs, shell, git, imports); `deep` adds timing and web."""
    results = [run_fs_check(root), run_shell_check(), run_git_check(root),
               run_imports_check(root)]
    if deep:
        results.extend([run_timing_check(), run_web_check(url)])
    return results


def build_report(root: Path, results: List[CheckResult], deep: bool) -> Dict[str, object]:
    """The JSON-ready report: schema, interpreter facts, one dict per check, counts."""
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": root.name,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "deep": deep,
        "checks": [result.as_dict() for result in results],
        "passed": sum(1 for result in results if result.passed),
        "total": len(results),
    }


def report_path(root: Path) -> Path:
    """The default report location: reports/probe-report-<UTC stamp>.json."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return root / REPORT_DIR_NAME / f"probe-report-{stamp}.json"


def write_report(root: Path, report: Dict[str, object], out: Optional[str] = None) -> Path:
    """Write the report as JSON and return its path."""
    target = Path(out) if out else report_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def print_table(report: Dict[str, object]) -> None:
    """Terse one-line-per-check table of what the battery observed."""
    for entry in report["checks"]:
        status = "PASS" if entry["passed"] else "FAIL"
        print(f"{entry['name']:<8} {status:<4} {entry['ms']:>8.1f} ms  {entry['evidence']}")
    print(f"probe: {report['passed']}/{report['total']} checks passed")


def build_parser() -> argparse.ArgumentParser:
    """The probe CLI: `run` (the battery) and `checks` (list the check ids)."""
    parser = argparse.ArgumentParser(
        prog="probe.py",
        description="Run the capability battery and write a verifiable JSON report.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the battery (fs, shell, git, imports [+ deep])")
    run.add_argument("--deep", action="store_true", help="also run timing and web")
    run.add_argument("--url", default=DEFAULT_WEB_URL,
                     help=f"URL for the web check (default: {DEFAULT_WEB_URL})")
    run.add_argument("--json", action="store_true",
                     help="print the report as JSON instead of the table")
    run.add_argument("--out", default=None,
                     help="report path (default: reports/probe-report-<UTC stamp>.json)")
    sub.add_parser("checks", help="list the check ids and what each measures")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point; 0 when every check passed, 1 when any failed."""
    args = build_parser().parse_args(argv)
    root = Path.cwd()
    if args.command == "checks":
        for name, description in CHECK_DESCRIPTIONS.items():
            print(f"{name:<8} {description}")
        return 0
    results = run_battery(root, deep=args.deep, url=args.url)
    report = build_report(root, results, deep=args.deep)
    target = write_report(root, report, out=args.out)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_table(report)
        print(f"report: {target}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
