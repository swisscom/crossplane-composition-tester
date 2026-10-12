#!/usr/bin/env python3
# Copyright 2023 Swisscom (Schweiz) AG

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parallel runner for the crossplane composition tests.

Discovers all feature directories under the given tests path and runs each one in its
own behave process, with a bounded pool of parallel workers. The full behave output of
each feature directory is captured into a log file under the logs directory, while the
console only shows one progress line per feature directory and a summary of the
failures at the end.

Typically invoked through tests_runner.sh, but can also be used directly:

    python3 parallel_runner.py .target_project/composition-tests --jobs 8
    python3 parallel_runner.py .target_project/composition-tests -t s3 --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from behave.parser import parse_file

if TYPE_CHECKING:  # imported lazily at runtime, see generate_coverage()
    from steps.coverage.models import CoverageReport

logger = logging.getLogger("xplane-composition-tester logger")

LOGS_DIR_DEFAULT = "logs"
JUNIT_DIR = "reports"
ALLURE_DIR = "allure_reports"
CUCUMBER_DIR = "cucumber_reports"

# Behave reads this variable in environment.py to enable coverage inside a behave process.
# The parallel runner owns coverage generation itself, so it must never reach the workers.
COVERAGE_ENV_VAR = "COMPOSITION_TESTER_COVERAGE"

# Lines like "5 scenarios passed, 1 failed, 0 skipped" from the behave summary
SCENARIO_SUMMARY_RE = re.compile(r"^(?P<counts>.*\bscenarios? .*(passed|failed|skipped).*)$", re.MULTILINE)
COUNT_RE = re.compile(r"(\d+)\s+(?:scenarios?\s+)?(passed|failed|error(?:ed)?|skipped|untested)")


@dataclass
class UnitResult:
    """Outcome of one behave process run on one feature directory."""
    name: str
    path: Path
    log_path: Path
    returncode: int = 0
    duration: float = 0.0
    output: str = ""
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    scenarios_skipped: int = 0

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Console:
    """Thread-safe console output with optional colors."""

    def __init__(self, use_color: bool):
        self.use_color = use_color
        self._lock = threading.Lock()

    def _c(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.use_color else text

    def green(self, text: str) -> str:
        return self._c("32", text)

    def red(self, text: str) -> str:
        return self._c("31", text)

    def yellow(self, text: str) -> str:
        return self._c("33", text)

    def bold(self, text: str) -> str:
        return self._c("1", text)

    def dim(self, text: str) -> str:
        return self._c("2", text)

    def print(self, *args, **kwargs):
        with self._lock:
            print(*args, **kwargs)
            sys.stdout.flush()


def discover_feature_directories(tests_path: Path) -> list[Path]:
    """Find all directories under tests_path that directly contain at least one .feature file."""
    feature_dirs = {feature.parent for feature in tests_path.glob("**/*.feature")}
    return sorted(feature_dirs)


def unit_weight(unit: Path) -> int:
    """Expanded scenario count of a unit's feature files (Scenario Outlines count one per
    Examples row), used to launch the heaviest units first: the total wall time is bounded
    by the longest-running directory, so it must not start late. Tag filters are not
    applied here — a rough ranking is enough for scheduling."""
    total = 0
    for feature_file in unit.glob("*.feature"):
        try:
            total += len(parse_file(str(feature_file)).walk_scenarios())
        except Exception:
            total += 1  # unparseable: let the behave worker report the error; keep a nonzero weight
    return total


def prewarm_schema_cache(console: "Console") -> None:
    """Populate the crossplane CLI schema cache once, before the parallel workers start.

    'crossplane resource validate' ('crossplane beta validate' before CLI v2.3) downloads base schemas into a shared cache (~/.crossplane/cache)
    on first use. Running many validators concurrently against a cold cache makes them race on
    that download and read half-written files ("cannot parse YAML manifest"). One warm-up
    validation downloads it sequentially; the workers then only read the cache. Empty inputs
    (/dev/null) trigger the download without needing anything to validate.
    """
    from steps.utils.checkers import _crossplane_validate_command

    start = time.monotonic()
    try:
        subprocess.run([*_crossplane_validate_command(), "/dev/null", "/dev/null"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    except Exception as exc:  # best-effort: on failure the workers just fall back to racing
        console.print(console.dim(f"Schema cache warm-up skipped: {exc}"))
        return
    console.print(console.dim(f"Schema cache warm ({time.monotonic() - start:.1f}s)"))


def unit_name(unit: Path, tests_path: Path) -> str:
    """Readable name of the feature directory, relative to the tests path."""
    try:
        return str(unit.relative_to(tests_path))
    except ValueError:
        return unit.name


def runner_fingerprint() -> str:
    """Short content hash of this file.

    Printed at startup so the log unambiguously identifies which build of the runner
    executed, independently of the container image tag that was requested.
    """
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    except OSError:
        return "unknown"


def build_behave_command(unit: Path, name: str, args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, "-m", "behave", "--junit", "--junit-directory", str(args.junit_dir), "--no-color"]
    if args.reports:
        cmd += ["-f", "allure_behave.formatter:AllureFormatter", "-o", str(args.allure_dir)]
        # the cucumber json formatter writes a single file, so it needs a unique path per worker
        cucumber_path = Path(f"{args.cucumber_dir}/{name}/cucumber_report.json")
        cucumber_path.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-f", "cucumber_json:PrettyCucumberJSONFormatter", "-o", str(cucumber_path)]
    cmd += ["-f", "pretty"]
    for tag in args.tags:
        cmd += ["-t", tag]
    cmd.append(str(unit))
    return cmd


def parse_scenario_counts(result: UnitResult):
    """Extract scenario pass/fail/skip counts from the behave console summary."""
    match = SCENARIO_SUMMARY_RE.search(result.output)
    if not match:
        return
    for count, status in COUNT_RE.findall(match.group("counts")):
        if status == "passed":
            result.scenarios_passed = int(count)
        elif status in ("failed", "error", "errored"):
            result.scenarios_failed += int(count)
        elif status == "skipped":
            result.scenarios_skipped = int(count)


ERROR_MARKERS = ("ASSERT FAILED", "Assertion Failed", "HOOK-ERROR", "ParserError",
                 "ConfigError", "Traceback (most recent call last)")


def extract_failure_details(output: str, max_lines: int = 60) -> list[str]:
    """Pull the interesting failure lines out of a behave log: each failing step with
    its (possibly multiline) error message, and the 'Failing scenarios:' block. Falls
    back to the tail of the log when behave crashed before producing a summary
    (e.g. configuration or parse errors)."""
    lines = output.splitlines()
    error_blocks: dict[tuple, int] = {}  # ordered: identical error blocks are collapsed with a repeat count
    failing_scenarios = []

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("Failing scenarios:"):
            failing_scenarios.append(stripped)
            i += 1
            while i < len(lines) and lines[i].strip():
                failing_scenarios.append(f"  {lines[i].strip()}")
                i += 1
            continue

        if stripped.startswith(ERROR_MARKERS):
            indent = len(lines[i]) - len(lines[i].lstrip())
            block = []
            # include the failing step itself (previous non-empty line, without the '# location' comment)
            for j in range(i - 1, -1, -1):
                if lines[j].strip():
                    block.append(lines[j].strip().split("  #")[0].rstrip())
                    break
            block.append(f"  {stripped}")
            i += 1
            # the error message can span multiple lines: keep going while indented and non-blank
            while i < len(lines) and lines[i].strip() and (len(lines[i]) - len(lines[i].lstrip())) >= indent:
                block.append(f"  {lines[i].strip()}")
                i += 1
            error_blocks[tuple(block)] = error_blocks.get(tuple(block), 0) + 1
            continue

        i += 1

    details = []
    for block, count in error_blocks.items():
        details += list(block)
        if count > 1:
            details.append(f"  (same failure repeated in {count} scenarios)")
    details += failing_scenarios

    if not details:
        details = ["(no behave failure summary found, log tail follows)"]
        details += [f"  {line}" for line in lines[-15:]]

    if len(details) > max_lines:
        details = details[:max_lines] + [f"... ({len(details) - max_lines} more lines, see full log)"]
    return details


def run_unit(unit: Path, name: str, log_dir: Path, args: argparse.Namespace, env: dict) -> UnitResult:
    log_path = log_dir / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    result = UnitResult(name=name, path=unit, log_path=log_path)

    cmd = build_behave_command(unit, name, args)
    start = time.monotonic()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, env=env)
    result.duration = time.monotonic() - start
    result.returncode = proc.returncode
    result.output = proc.stdout or ""

    log_path.write_text(f"$ {' '.join(cmd)}\n\n{result.output}", encoding="utf-8")
    parse_scenario_counts(result)
    return result


def format_progress_line(result: UnitResult, done: int, total: int, console: Console) -> str:
    status = console.green("PASS") if result.ok else console.red("FAIL")
    counts = f"{result.scenarios_passed} passed"
    if result.scenarios_failed:
        counts += f", {result.scenarios_failed} failed"
    if result.scenarios_skipped:
        counts += f", {result.scenarios_skipped} skipped"
    line = f"[{done:>3}/{total}] {status} {result.name:<40} {counts:<30} ({result.duration:5.1f}s)"
    if not result.ok:
        line += console.dim(f"  log: {result.log_path}")
    return line


def print_failure_summary(failed: list[UnitResult], console: Console):
    console.print("\n" + console.bold("=" * 25 + " FAILURE SUMMARY " + "=" * 25))
    for result in failed:
        console.print(f"\n{console.red('✗ ' + result.name)}  {console.dim(str(result.log_path))}")
        for line in extract_failure_details(result.output):
            console.print(f"  {line}")
    console.print()


def generate_coverage(tests_path: Path, console: Console, allure_dir: Path | None = None) -> None:
    """Generate the parameter coverage report once for the whole test suite.

    In parallel mode the coverage generation is removed from the behave workers
    (it is a static analysis of the whole suite, so each worker would redo it and
    emit its own partial report) and run a single time here instead.

    This is a whole-suite static analysis that can take several seconds with no
    sub-output, so it is bracketed with start/done logs (flushed via Console) to
    make clear the runner is still working and not hung after the tests finished.

    Args:
        tests_path: directory holding the feature directories; its parent is the
            project root that must contain both ``pkg/`` and ``composition-tests/``.
        console: thread-safe console used for all user-facing output.
        allure_dir: Allure *results* directory. When given, a single synthetic
            Allure result entry is written so the coverage report shows up in the
            generated HTML report. ``None`` disables the Allure integration.
    """
    from steps.coverage.reporter import generate_coverage_report, print_coverage_summary, save_coverage_report

    test_root = tests_path.parent
    console.print(f"\nGenerating coverage report for the whole suite (test root: {test_root}) — this can take a few seconds ...")
    start = time.monotonic()

    try:
        report = generate_coverage_report(test_root)
    except Exception as exc:  # defensive: coverage is a report, it must not fail the test run
        logger.exception("Coverage report generation failed")
        console.print(console.red(f"✗ Error generating coverage report: {exc}"))
        return

    # The Allure entry is written first and in its own try block: it is the only coverage
    # output that survives into the published HTML report, so a failure in the console
    # summary (which also runs the requirements validation) or in the JSON/YAML dump must
    # never be able to suppress it.
    if allure_dir is not None:
        try:
            _write_coverage_allure_result(report, allure_dir, console)
        except Exception as exc:
            logger.exception("Writing the coverage Allure result failed")
            console.print(console.red(f"✗ Error writing the coverage Allure result: {exc}"))

    try:
        print_coverage_summary(report)
        save_coverage_report(report, test_root.parent / "coverage-report.json", format="json")
        save_coverage_report(report, test_root.parent / "coverage-report.yaml", format="yaml")
        console.print(console.dim(f"Coverage report written to coverage-report.json / .yaml ({time.monotonic() - start:.1f}s)"))
    except Exception as exc:
        logger.exception("Printing or saving the coverage report failed")
        console.print(console.red(f"✗ Error saving coverage report: {exc}"))


@dataclass(frozen=True)
class _CoverageSummary:
    """Rendered representations of a coverage report, ready to be attached to Allure."""
    text: str
    html: str


@dataclass(frozen=True)
class _AllureAttachment:
    """One file attached to an Allure result entry."""
    name: str
    source: str
    mime_type: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to the shape expected in an Allure ``*-result.json`` file."""
        return {"name": self.name, "source": self.source, "type": self.mime_type}


def _format_percentage(value: float) -> str:
    """Format a coverage ratio for display, tolerating missing or malformed values."""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _render_coverage_text(report: CoverageReport) -> str:
    """Render the per-composition definition-parameter coverage as a plain text summary."""
    lines = ["CROSSPLANE COMPOSITION COVERAGE SUMMARY", "=" * 60, ""]
    for name, coverage in sorted(report.parameter_coverage_by_composition.items()):
        lines.append(f"Composition: {name}")
        lines.append(
            f"  Coverage: {coverage.coverage_percentage:.1f}% "
            f"({coverage.parameters_covered}/{coverage.parameters_total} parameters)"
        )
        for marker, parameters in (("✓ Covered", coverage.covered_parameters),
                                   ("✗ Uncovered", coverage.uncovered_parameters)):
            if not parameters:
                continue
            lines.append(f"  {marker}: {', '.join(parameters[:10])}")
            if len(parameters) > 10:
                lines.append(f"    ... and {len(parameters) - 10} more")
        lines.append("")
    return "\n".join(lines)


def _render_coverage_html(report: CoverageReport) -> str:
    """Render the coverage report as a self-contained HTML table for the Allure UI."""
    rows: list[str] = []
    for name, parameters in sorted(report.parameter_coverage_by_composition.items()):
        resources = report.managed_resource_coverage_by_composition.get(name)
        statements = report.statement_coverage_by_composition.get(name)
        per_resource = report.resource_parameter_coverage_by_composition.get(name, {})

        total_params = sum(rc.parameters_total for rc in per_resource.values())
        covered_params = sum(rc.parameters_covered for rc in per_resource.values())
        average = (covered_params / total_params * 100.0) if total_params else 0.0

        cells = [
            escape(name),
            f"{parameters.parameters_covered}/{parameters.parameters_total} "
            f"({_format_percentage(parameters.coverage_percentage)})",
            f"{resources.resources_covered}/{resources.resources_total} "
            f"({_format_percentage(resources.coverage_percentage)})" if resources else "n/a",
            _format_percentage(average),
            f"{statements.covered_statements}/{statements.total_statements} "
            f"({_format_percentage(statements.coverage_percentage)})" if statements else "n/a",
        ]
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")

    return (
        "<html><body>"
        "<h2>Crossplane Composition Coverage</h2>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr>"
        "<th>Composition</th>"
        "<th>Definition parameters</th>"
        "<th>Managed resources</th>"
        "<th>Avg params/resource</th>"
        "<th>Statements</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
        "</body></html>"
    )


def _write_allure_attachment(allure_dir: Path, content: str, extension: str, name: str,
                             mime_type: str) -> _AllureAttachment:
    """Write one attachment file into the Allure results directory and describe it."""
    source = f"{uuid.uuid4()}-attachment.{extension}"
    with (allure_dir / source).open("w", encoding="utf-8") as handle:
        handle.write(content)
    return _AllureAttachment(name=name, source=source, mime_type=mime_type)


def _write_coverage_allure_metadata(report: CoverageReport, allure_dir: Path) -> None:
    """Write the Allure report-level metadata files describing the coverage run.

    ``environment.properties`` is what renders the per-composition coverage list in the
    Environment widget on the Allure overview page. In sequential mode ``after_all()``
    in ``environment.py`` writes these; in parallel mode coverage runs in the parent
    process instead, so they have to be written here or the widget is simply absent.
    """
    env_lines = []
    for composition_name, coverage in sorted(report.parameter_coverage_by_composition.items()):
        # Property keys must not contain separators that Allure's parser treats specially.
        key = composition_name.replace("-", "_").replace("/", ".").replace(" ", "_")
        env_lines.append(f"Coverage.{key}={coverage.coverage_percentage:.1f}%")
        env_lines.append(f"Coverage.{key}.covered={coverage.parameters_covered}/{coverage.parameters_total}")
    (allure_dir / "environment.properties").write_text("\n".join(env_lines), encoding="utf-8")

    categories = [{"name": "Parameter Coverage", "messageRegex": ".*coverage.*", "traceRegex": ".*"}]
    (allure_dir / "categories.json").write_text(json.dumps(categories, indent=2), encoding="utf-8")

    executor = {
        "name": "Crossplane Composition Tester",
        "type": "behave",
        "reportName": "Test Report with Coverage",
        "buildName": "Coverage Report",
    }
    (allure_dir / "executor.json").write_text(json.dumps(executor, indent=2), encoding="utf-8")


def _write_coverage_allure_result(report: CoverageReport, allure_dir: Path, console: Console) -> None:
    """Write the coverage report as a single synthetic Allure result entry.

    The Allure Behave formatter only emits results for real scenarios, and
    ``allure.attach()`` requires an active test case, which does not exist once the
    behave workers have exited. Writing the ``*-result.json`` file directly is the
    supported way to add a standalone entry: ``allure generate`` treats it like any
    other test. Exactly one entry is produced per run, because this runs in the
    parent process after all workers have finished.
    """
    allure_dir.mkdir(parents=True, exist_ok=True)
    _write_coverage_allure_metadata(report, allure_dir)
    summary = _CoverageSummary(text=_render_coverage_text(report), html=_render_coverage_html(report))

    attachments = [
        _write_allure_attachment(allure_dir, summary.html, "html",
                                 "Coverage Summary (HTML)", "text/html"),
        _write_allure_attachment(allure_dir, report.to_json(), "json",
                                 "Coverage Report (raw JSON)", "application/json"),
        _write_allure_attachment(allure_dir, report.to_yaml(), "yaml",
                                 "Coverage Report (raw YAML)", "text/yaml"),
        _write_allure_attachment(allure_dir, summary.text, "txt",
                                 "Coverage Summary (text)", "text/plain"),
    ]

    now_ms = int(time.time() * 1000)
    result = {
        "uuid": str(uuid.uuid4()),
        # Stable across runs so Allure can build a history/trend for the entry.
        "historyId": hashlib.md5(b"coverage-summary").hexdigest(),
        "name": "Coverage Summary",
        "fullName": "Coverage: Summary",
        "status": "passed",
        "stage": "finished",
        "start": now_ms,
        "stop": now_ms,
        "labels": [
            {"name": "suite", "value": "Coverage"},
            {"name": "framework", "value": "behave"},
            {"name": "language", "value": "cpython3"},
        ],
        "attachments": [attachment.to_dict() for attachment in attachments],
    }

    with (allure_dir / f"{result['uuid']}-result.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle)
    console.print(console.dim(f"Coverage Summary written into Allure results: {allure_dir}"))


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run crossplane composition tests in parallel with behave")
    parser.add_argument("tests_path", type=Path,
                        help="directory containing the feature directories (e.g. .target_project/composition-tests)")
    parser.add_argument("-j", "--jobs", type=int, default=min(10, os.cpu_count() or 4),
                        help="number of feature directories to run in parallel (default: %(default)s)")
    parser.add_argument("-t", "--tags", action="append", default=[],
                        help="tags to filter the scenarios, passed through to behave (repeatable, combined with AND)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print the full behave output of each feature directory as it completes")
    parser.add_argument("--reports", action="store_true",
                        help="also generate Allure and Cucumber JSON reports")
    parser.add_argument("--coverage", action="store_true",
                        help="generate the parameter coverage report after the tests")
    parser.add_argument("--logs-dir", type=Path, default=Path(LOGS_DIR_DEFAULT),
                        help="directory for the captured behave logs (default: %(default)s)")
    # Output dirs are configurable so non-local runners (e.g. a CI pipeline) can point them
    # at a writable mounted volume and the location the report step expects.
    parser.add_argument("--junit-dir", type=Path, default=Path(JUNIT_DIR),
                        help="directory for the JUnit XML reports (default: %(default)s)")
    parser.add_argument("--allure-dir", type=Path, default=Path(ALLURE_DIR),
                        help="directory for the Allure results, when --reports is set (default: %(default)s)")
    parser.add_argument("--cucumber-dir", type=Path, default=Path(CUCUMBER_DIR),
                        help="directory for the Cucumber JSON reports, when --reports is set (default: %(default)s)")
    parser.add_argument("--no-color", action="store_true", help="disable colored output")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    console = Console(use_color=sys.stdout.isatty() and not args.no_color)
    console.print(console.dim(f"parallel_runner.py build {runner_fingerprint()}"))

    if not args.tests_path.is_dir():
        console.print(console.red(f"ERROR: tests path '{args.tests_path}' is not a directory"))
        return 2

    units = discover_feature_directories(args.tests_path)
    if not units:
        console.print(console.red(f"ERROR: no .feature files found under '{args.tests_path}'"))
        return 2
    # Heaviest units first: workers pick up units in submission order, so the largest
    # directory starts immediately instead of stretching the wall time from a late start.
    units.sort(key=unit_weight, reverse=True)

    jobs = max(1, min(args.jobs, len(units)))
    # Only needed when validators run concurrently; a sequential run cannot race on the cache.
    if jobs > 1:
        prewarm_schema_cache(console)
    args.logs_dir.mkdir(parents=True, exist_ok=True)
    # pre-create shared report directories so parallel behave processes don't race on mkdir
    args.junit_dir.mkdir(parents=True, exist_ok=True)
    if args.reports:
        args.allure_dir.mkdir(parents=True, exist_ok=True)
        args.cucumber_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    # the steps and the cucumber_json formatter are imported from this directory
    _runner_dir = str(Path(__file__).parent)
    _existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_runner_dir}{os.pathsep}{_existing_pythonpath}" if _existing_pythonpath else _runner_dir
    # Coverage is generated once by this runner (see generate_coverage), never by the workers:
    # each one would redo the whole-suite analysis and emit its own partial Allure entry.
    # The variable is popped unconditionally, so it is stripped from the worker environment
    # even when coverage was requested through --coverage instead of the environment.
    coverage_from_env = env.pop(COVERAGE_ENV_VAR, "").lower() == "true"
    coverage_requested = args.coverage or coverage_from_env

    console.print(f"Discovered {len(units)} feature directories under {args.tests_path}")
    console.print(f"Running with {jobs} parallel workers. Full logs in: {args.logs_dir}/\n")

    results: list[UnitResult] = []
    done = 0
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(run_unit, unit, unit_name(unit, args.tests_path), args.logs_dir, args, env): unit
            for unit in units
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done += 1
            console.print(format_progress_line(result, done, len(units), console))
            if args.verbose:
                console.print(console.dim(f"--- full output of {result.name} " + "-" * 30))
                console.print(result.output)
                console.print(console.dim("-" * 60))
    total_duration = time.monotonic() - start

    failed = sorted((r for r in results if not r.ok), key=lambda r: r.name)
    if failed:
        print_failure_summary(failed, console)

    scenarios_passed = sum(r.scenarios_passed for r in results)
    scenarios_failed = sum(r.scenarios_failed for r in results)
    summary = (f"{len(units)} feature directories: {len(units) - len(failed)} passed, {len(failed)} failed | "
               f"scenarios: {scenarios_passed} passed, {scenarios_failed} failed | "
               f"took {int(total_duration // 60)}m{total_duration % 60:04.1f}s")
    console.print(console.bold(console.red(summary) if failed else console.green(summary)))
    if failed:
        console.print(console.dim(f"Full behave output of the failed runs: "
                                  + ", ".join(str(r.log_path) for r in failed)))

    if coverage_requested:
        allure_dir = args.allure_dir if args.reports else None
        generate_coverage(args.tests_path, console, allure_dir=allure_dir)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
