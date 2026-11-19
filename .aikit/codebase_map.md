# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document catalogues Python modules, classes, and exported functions. See Map Coverage for any stack it does not index.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `6`
- **Total Classes**: `7`
- **Total Top-Level Functions**: `20`
- **Total Class Methods**: `14`
- **Total Source Lines**: `502`

## 🧭 Map Coverage
- **Indexed**: python (`6` module(s))
- **Not indexed by this map**: none (no non-Python source files were found)

---

## 📦 Modules & Exported Symbols

### [`demo.py`](demo.py)
> *Headless scripted drive: prints WORLD-DELTA lines, no input, exits 0.*

**Size**: `22` lines

**Functions:**
- `def _parse_seed(argv)`

---

### [`inventory.py`](inventory.py)
> *Project-owned UI inventory: one `kind|name|locator` line per control.*

**Size**: `6` lines

---

### [`probe.py`](probe.py)
> *probe.py - a local-first capability probe for the agent workspace.*

**Size**: `336` lines

**Classes:**
- `class CheckResult` - *One falsifiable measurement: what passed, the evidence observed, the cost in ms.*
  - Method `.as_dict()` - *The JSON-ready record of this check.*

**Functions:**
- `def _elapsed_ms(started)` - *Milliseconds since `started`, rounded to a clean value.*
- `def _short(text, limit)` - *One line, truncated to `limit` characters, for evidence text.*
- `def _subprocess(argv, cwd, timeout)` - *Run one argv as a list (never a shell string) and return (exit, out, err).*
- `def run_fs_check(root)` - *Round-trip a file in the project tree: write it, read it back, delete it.*
- `def run_shell_check()` - *`python --version` through sys.executable (argv list, 10 s timeout).*
- `def run_git_check(root)` - *Is the tree inside a git work tree? (`git rev-parse --is-inside-work-tree`.)*
- `def _iter_project_files(root)` - *All .py files in the project tree, sorted (excluding .git internals).*
- `def imports_scan(root)` - *Third-party imports across the project's .py files, plus the unparseable ones.*
- `def run_imports_check(root)` - *No third-party imports anywhere in the project tree (AST only).*
- `def run_timing_check()` - *Wall time of `python -c pass` against TIMING_BUDGET_MS.*
- `def body_digest(data)` - *The SHA-256 digest of the web response body, recorded as evidence.*
- `def run_web_check(url)` - *GET `url`; record the status, body size and digest of the response.*
- `def run_battery(root, deep, url)` - *The default battery (fs, shell, git, imports); `deep` adds timing and web.*
- `def build_report(root, results, deep)` - *The JSON-ready report: schema, interpreter facts, one dict per check, counts.*
- `def report_path(root)` - *The default report location: reports/probe-report-<UTC stamp>.json.*
- `def write_report(root, report, out)` - *Write the report as JSON and return its path.*
- `def print_table(report)` - *Terse one-line-per-check table of what the battery observed.*
- `def build_parser()` - *The probe CLI: `run` (the battery) and `checks` (list the check ids).*
- `def main(argv)` - *CLI entry point; 0 when every check passed, 1 when any failed.*

---

### [`tests/__init__.py`](tests/__init__.py)
> *The probe project's tests package.*

**Size**: `1` lines

---

### [`tests/test_probe.py`](tests/test_probe.py)
> *Unit tests for probe's pure functions and checks (all local, fast).*

**Size**: `94` lines

**Classes:**
- `class DigestTest`
  - Method `.test_body_digest_of_empty_is_the_well_known_vector()`
  - Method `.test_body_digest_changes_with_content()`
- `class CheckResultTest`
  - Method `.test_as_dict_records_all_fields()`
- `class ImportsScanTest`
  - Method `._write(root, name, text)`
  - Method `.test_stdlib_and_local_imports_are_not_third_party()`
  - Method `.test_flags_a_third_party_import_by_name()`
  - Method `.test_records_unparseable_files_without_raising()`
- `class FsCheckTest`
  - Method `.test_roundtrip_passes_and_cleans_up()`
- `class BuildReportTest`
  - Method `.test_report_counts_and_preserves_check_order()`
  - Method `.test_write_report_round_trips_through_json()`

---

### [`tests/test_probe_cli.py`](tests/test_probe_cli.py)
> *Integ tests: the probe CLI runs the battery end-to-end in the project root.*

**Size**: `43` lines

**Classes:**
- `class RunCliTest`
  - Method `._run(*args, timeout)`
  - Method `.test_default_battery_passes_and_report_round_trips()`
  - Method `.test_deep_battery_adds_timing_and_web_checks()`

---
