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
import os
from pathlib import Path
import json
from html import escape
import time
import uuid
import hashlib

from behave import fixture, use_fixture
from behave.runner import Context

from steps.coverage.reporter import generate_coverage_report, print_coverage_summary, save_coverage_report

COMPOSITION_TESTER_FUNCTIONS_FILE_ON_CI = "COMPOSITION_TESTER_FUNCTIONS_FILE"

def _find_tests_root(base_path: Path) -> Path:
    """
    Find the tests root directory by walking up from the base path.
    The tests root is identified by the presence of functions.yaml or by standard directory names.
    
    Args:
        base_path: The starting path (feature directory)
        
    Returns:
        Path to the tests root directory
    """
    tests_root_candidates = ["composition-tests", "test", "tests"]
    current_path = base_path
    
    # Walk up the directory tree to find the tests root
    while current_path.parent != current_path:  # Not at filesystem root
        # Check if current directory is the tests root
        # It should contain functions.yaml or be one of the standard test directory names
        if (current_path / "functions.yaml").exists() or \
           (current_path / "functions-ci.yaml").exists() or \
           current_path.name in tests_root_candidates:
            return current_path
        
        current_path = current_path.parent
    
    # Fallback: assume parent of base_path is tests root (backward compatible)
    return base_path.parent

@fixture
def setup_base_path(ctx: Context, feature):
    """Retrieve the base path for the feature file. The base path is the path to the
    feature folder containing the feature file.

    Arguments:
        ctx {Context} -- behave context

    Raises:
        ValueError: no filename attribute found inside feature in context
    """
    filename = getattr(feature, "filename", None)
    if filename is None:
        raise ValueError(f"no filename attribute found inside feature in context")

    base_path = Path(filename).parent
    ctx.base_path = base_path


@fixture
def setup_envconfig_filepath(ctx: Context):
    """Setup the environment config filepath and save it in the context. By convention, the environment config file should be at the same
     level as the directory containing all features folders. Also by convention the file is named "envconfig.yaml"

    Example:
    ├── features
        ├── feature 1
            ├──
            ├──
        ├── feature 2
            ├──
            ├──
        ├── envconfig.json       # Environment Configuration File

    Arguments:
        ctx {Context} -- behave context
    """
    # Find the tests root directory (works for any nesting level)
    tests_root = _find_tests_root(ctx.base_path)
    ctx.envconfigs_folder_path = tests_root
    envconfig_filepath = tests_root / "envconfig.yaml"
    
    # Check if file exists
    if envconfig_filepath.exists():
        ctx.envconfig_filepath = envconfig_filepath


@fixture
def setup_functions_filepath(ctx: Context):
    """Setup the functions filepath and save it in the context. By convention, the functions file should be at the same
     level as the directory containing all features folders. Also by convention the file is named "functions.yaml". 

    Example:
    ├── features
        ├── feature 1
            ├──
            ├──
        ├── feature 2
            ├──
            ├──
        ├── functions.yaml             # Default functions File
        |── functions-ci.yaml          # Version of the functions file to run on CI
        

    Arguments:
        ctx {Context} -- behave context
    """
    # Find the tests root directory (works for any nesting level)
    tests_root = _find_tests_root(ctx.base_path)
    
    # Save the functions folder path in the context
    # By default, functions files are stored in the tests root directory
    ctx.functions_folder_path = tests_root
    if on_ci():
        ctx.on_ci = True
        # If running on CI, the default functions file is specified by the environment variable "COMPOSITION_TESTER_FUNCTIONS_FILE"
        ci_functions_file = os.environ[
            COMPOSITION_TESTER_FUNCTIONS_FILE_ON_CI
        ]  # e.g. "functions-ci.yaml"
        functions_filepath = tests_root / ci_functions_file
    else:
        ctx.on_ci = False
        # The default functions file used for testing is "functions.yaml"
        functions_filepath = tests_root / "functions.yaml"

    # Save the functions file path in the context
    ctx.functions_filepath = functions_filepath


@fixture
def setup_composition_filepath(ctx: Context):
    """Setup the composition path of the current feature and save it in the context. By convention, the compositions
    directory should be in the "pkg" folder at the root of the project. Also by convention the file is named
    "composition.yaml" and "definition.yaml".
    
    This function automatically mirrors the directory structure from composition-tests to pkg, supporting
    arbitrary nesting levels.

    Examples:
    
    Flat structure:
    ├── composition-tests
    │   ├── s3
    │   │   └── s3.feature
    │   └── dynamodb
    │       └── dynamodb.feature
    └── pkg
        ├── s3
        │   ├── composition.yaml
        │   └── definition.yaml
        └── dynamodb
            ├── composition.yaml
            └── definition.yaml
    
    Nested structure (any depth):
    ├── composition-tests
    │   ├── community
    │   │   ├── ses
    │   │   │   └── ses.feature
    │   │   └── sns
    │   │       └── sns.feature
    └── pkg
        ├── community
        │   ├── ses
        │   │   ├── composition.yaml
        │   │   └── definition.yaml
        │   └── sns
        │       ├── composition.yaml
        │       └── definition.yaml
    """
    # Start from the feature directory (e.g., /path/to/composition-tests/community/ses)
    # Find the tests root directory using the shared helper function
    tests_root = _find_tests_root(ctx.base_path)
    
    # The project root is the parent of the tests root
    project_root = tests_root.parent
    ctx.project_root = project_root
    
    # Calculate the relative path from tests_root to the feature directory
    # This gives us the path to mirror under pkg/
    try:
        relative_path = ctx.base_path.relative_to(tests_root)
    except ValueError:
        # Fallback: just use the feature directory name
        relative_path = Path(ctx.base_path.name)
    
    # Build the composition directory path by mirroring the structure under pkg/
    compositions_directory = project_root / "pkg" / relative_path
    
    ctx.compositions_directory = compositions_directory
    ctx.composition_filepath = compositions_directory / "composition.yaml"
    ctx.definition_filepath = compositions_directory / "definition.yaml"

@fixture
def setup_from_environment(ctx: Context):
    """Get the environment variables and set them in the context
    """
    
    ctx.debug_mode = os.environ.get("COMPOSITION_TESTER_DEBUG_MODE", "False").lower() == "true"
    ctx.coverage_mode = os.environ.get("COMPOSITION_TESTER_COVERAGE", "False").lower() == "true"
    
    # Also check behave userdata for coverage flag (-D coverage=true)
    if hasattr(ctx, 'config') and hasattr(ctx.config, 'userdata'):
        if ctx.config.userdata.get('coverage', '').lower() == 'true':
            ctx.coverage_mode = True
    
    
def before_feature(context, feature):
    use_fixture(setup_base_path, context, feature)
    use_fixture(setup_envconfig_filepath, context)
    use_fixture(setup_functions_filepath, context)
    use_fixture(setup_composition_filepath, context)
    use_fixture(setup_from_environment, context)


def on_ci():
    # check special environment variable to determine if running locally or in CI pipeline
    return COMPOSITION_TESTER_FUNCTIONS_FILE_ON_CI in os.environ

def before_scenario(context: Context, scenario):
    """
    If debug mode is enabled, create an 'execution' folder for the current
    scenario inside the feature folder, and store that path in context.
    Otherwise, skip creating any new folder.
    """
    # Track actually executed feature files for coverage reporting.
    # This is more accurate than scanning the filesystem, especially when users
    # run only a subset of features/scenarios.
    if getattr(context, 'coverage_mode', False):
        feature_obj = getattr(scenario, 'feature', None) or getattr(context, 'feature', None)
        filename = getattr(feature_obj, 'filename', None)
        if filename:
            if not hasattr(context, 'executed_feature_files') or context.executed_feature_files is None:
                context.executed_feature_files = set()
            context.executed_feature_files.add(str(Path(filename).resolve()))

    if not context.debug_mode:
        context.execution_folder = None
        return

    base_path = context.base_path if isinstance(context.base_path, Path) else Path(context.base_path)
    execution_dir = base_path / "execution"
    execution_dir.mkdir(parents=True, exist_ok=True)
    
    scenario_name_safe = "".join(c if c.isalnum() or c in ('-', '_') else "_" for c in scenario.name)
    scenario_dir = execution_dir / scenario_name_safe
    scenario_dir.mkdir(parents=True, exist_ok=True)
    
    context.execution_folder = scenario_dir

def after_scenario(context: Context, scenario):
    """
    If debug mode is enabled, you can log the folder name or perform any additional
    cleanup. Otherwise, nothing happens.
    """
    if context.debug_mode and context.execution_folder:
        print(f"DEBUG MODE ON - Scenario '{scenario.name}' dumps stored in: {context.execution_folder}")


def before_all(context: Context):
    """
    Initialize coverage tracking if enabled.
    """
    use_fixture(setup_from_environment, context)
    
    if getattr(context, 'coverage_mode', False):
        # Populated in before_scenario for scenarios that actually execute.
        context.executed_feature_files = set()
        print("\n" + "=" * 80)
        print("COVERAGE MODE ENABLED")
        print("=" * 80)
        print("✓ Parameter coverage will be calculated after tests complete")
        print("=" * 80 + "\n")


def after_all(context: Context):
    """
    Clean up per-process temp directory and generate coverage report if enabled.
    """
    import shutil
    from steps.utils.constants import _TMP_DIR
    shutil.rmtree(_TMP_DIR, ignore_errors=True)

    if not getattr(context, 'coverage_mode', False):
        return
    
    print("\n" + "=" * 80)
    print("GENERATING COVERAGE REPORT...")
    print("=" * 80 + "\n")
    
    # Determine test root directory
    # The context should have project_root set by before_feature
    test_root = None
    if hasattr(context, '_runner') and hasattr(context._runner, 'config'):
        # Get the first feature's base path to determine test root
        for feature in context._runner.features:
            if hasattr(feature, 'filename'):
                # The project root (containing pkg/ and the tests directory) is the parent of the
                # tests root, whatever the nesting depth of the feature directory.
                test_root = _find_tests_root(Path(feature.filename).parent).parent
                break
    
    # Fallback: try to find test directory from current working directory
    if test_root is None or not test_root.exists():
        cwd = Path.cwd()
        if (cwd / "test").exists():
            test_root = cwd / "test"
        elif cwd.name == "test":
            test_root = cwd
        else:
            print("✗ Could not determine test root directory")
            return
    
    print(f"Test root: {test_root}\n")
    
    # Generate coverage report
    try:
        executed_feature_files = None
        if hasattr(context, 'executed_feature_files') and context.executed_feature_files:
            executed_feature_files = {Path(p) for p in context.executed_feature_files}
            print(f"Executed feature files captured: {len(executed_feature_files)}")
        elif hasattr(context, '_runner') and hasattr(context._runner, 'features'):
            # Fallback: use whatever Behave loaded (may include skipped features)
            try:
                executed_feature_files = {Path(f.filename).resolve() for f in context._runner.features if hasattr(f, 'filename')}
            except Exception:
                executed_feature_files = None

        report = generate_coverage_report(test_root, executed_feature_files=executed_feature_files)
        
        # Print summary to console
        print_coverage_summary(report)

        # Same location as the parallel runner: next to the project directory
        save_coverage_report(report, test_root.parent / "coverage-report.json", format="json")
        save_coverage_report(report, test_root.parent / "coverage-report.yaml", format="yaml")
        
        # Create a formatted summary.
        # We intentionally DO NOT call `allure.attach()` here because `after_all()` often
        # runs without an active test-case context and Allure can throw KeyError(None).
        # Instead we always write a synthetic Allure result entry (below), which reliably
        # shows up in the HTML report.
        summary_lines = ["CROSSPLANE COMPOSITION COVERAGE SUMMARY", "=" * 60, ""]

        for comp_name, coverage in sorted(report.parameter_coverage_by_composition.items()):
            summary_lines.append(f"Composition: {comp_name}")
            summary_lines.append(
                f"  Coverage: {coverage.coverage_percentage:.1f}% ({coverage.parameters_covered}/{coverage.parameters_total} parameters)"
            )

            if coverage.covered_parameters:
                summary_lines.append(f"  ✓ Covered: {', '.join(coverage.covered_parameters[:10])}")
                if len(coverage.covered_parameters) > 10:
                    summary_lines.append(f"    ... and {len(coverage.covered_parameters) - 10} more")

            if coverage.uncovered_parameters:
                summary_lines.append(f"  ✗ Uncovered: {', '.join(coverage.uncovered_parameters[:10])}")
                if len(coverage.uncovered_parameters) > 10:
                    summary_lines.append(f"    ... and {len(coverage.uncovered_parameters) - 10} more")

            summary_lines.append("")

        summary_text = "\n".join(summary_lines)

        # Add a more readable HTML summary for the Allure UI.
        def _pct(val):
            try:
                return f"{float(val):.1f}%"
            except Exception:
                return "0.0%"

        html_rows = []
        for comp_name, cov in sorted(report.parameter_coverage_by_composition.items()):
                mr = report.managed_resource_coverage_by_composition.get(comp_name)
                st = report.statement_coverage_by_composition.get(comp_name)
                rp = report.resource_parameter_coverage_by_composition.get(comp_name, {})

                # Average per-resource param coverage
                if rp:
                    total_params = sum(rc.parameters_total for rc in rp.values())
                    covered_params = sum(rc.parameters_covered for rc in rp.values())
                    avg = (covered_params / total_params * 100) if total_params > 0 else 0.0
                else:
                    avg = 0.0

                cells = [
                    escape(comp_name),
                    f"{cov.parameters_covered}/{cov.parameters_total} ({_pct(cov.coverage_percentage)})",
                    f"{mr.resources_covered}/{mr.resources_total} ({_pct(mr.coverage_percentage)})" if mr else "n/a",
                    _pct(avg),
                    f"{st.covered_statements}/{st.total_statements} ({_pct(st.coverage_percentage)})" if st else "n/a",
                ]
                html_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")

        summary_html = (
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
            + "".join(html_rows) +
            "</tbody></table>"
            "</body></html>"
        )

        # Write Allure artifacts into the same *results* directory the Allure Behave formatter uses.
        def _determine_allure_results_dirs() -> list[Path]:
                candidates: list[Path] = []
                for env_var in ("ALLURE_RESULTS_DIR", "ALLURE_OUTPUT_DIR", "ALLURE_DIR"):
                    value = os.environ.get(env_var)
                    if value:
                        candidates.append(Path(value))

                candidates.append(Path("/tmp/allure-results"))
                candidates.append(test_root.parent / "allure_reports")

                # De-duplicate while preserving order
                uniq: list[Path] = []
                seen: set[str] = set()
                for p in candidates:
                    key = str(p)
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(p)

                # Ensure directories exist
                existing: list[Path] = []
                for candidate in uniq:
                    try:
                        candidate.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        continue
                    if candidate.exists() and candidate.is_dir():
                        existing.append(candidate)

                return existing or [test_root.parent / "allure_reports"]

        allure_results_dirs = _determine_allure_results_dirs()
        print(f"Allure results dirs for coverage artifacts: {', '.join(str(p) for p in allure_results_dirs)}")

        for allure_results_dir in allure_results_dirs:
                # Create Allure environment.properties file with coverage info
                env_props_path = allure_results_dir / "environment.properties"
                
                env_lines = []
                for comp_name, coverage in sorted(report.parameter_coverage_by_composition.items()):
                    safe_name = comp_name.replace("-", "_").replace(" ", "_")
                    env_lines.append(f"Coverage.{safe_name}={coverage.coverage_percentage:.1f}%")
                    env_lines.append(f"Coverage.{safe_name}.covered={coverage.parameters_covered}/{coverage.parameters_total}")
                
                with open(env_props_path, 'w') as f:
                    f.write("\n".join(env_lines))

                print(f"✓ Allure environment.properties created with coverage data in: {allure_results_dir}")

                # Create a custom categories.json to show coverage as a trend
                categories_path = allure_results_dir / "categories.json"
                categories = [
                    {
                        "name": "Parameter Coverage",
                        "messageRegex": ".*coverage.*",
                        "traceRegex": ".*"
                    }
                ]
                with open(categories_path, 'w') as f:
                    json.dump(categories, f, indent=2)

                # Create executor.json with coverage info
                executor_path = allure_results_dir / "executor.json"
                executor_data = {
                    "name": "Crossplane Composition Tester",
                    "type": "behave",
                    "reportName": "Test Report with Coverage",
                    "buildName": "Coverage Report"
                }
                with open(executor_path, 'w') as f:
                    json.dump(executor_data, f, indent=2)

                # Also create a dedicated Allure "test" entry for coverage so the attachments
                # reliably show up in the Allure UI (allure.attach() in after_all may not
                # be associated with any scenario/test case).
                now_ms = int(time.time() * 1000)
                coverage_uuid = str(uuid.uuid4())

                def _write_attachment(content: str, ext: str) -> str:
                    attachment_name = f"{uuid.uuid4()}-attachment.{ext}"
                    (allure_results_dir / attachment_name).write_text(content)
                    return attachment_name

                html_source = _write_attachment(summary_html, "html")
                json_source = _write_attachment(report.to_json(), "json")
                yaml_source = _write_attachment(report.to_yaml(), "yaml")
                text_source = _write_attachment(summary_text, "txt")

                history_id = hashlib.md5("coverage-summary".encode("utf-8")).hexdigest()
                result = {
                    "uuid": coverage_uuid,
                    "historyId": history_id,
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
                    "attachments": [
                        {"name": "Coverage Summary (HTML)", "source": html_source, "type": "text/html"},
                        {"name": "Coverage Report (raw JSON)", "source": json_source, "type": "application/json"},
                        {"name": "Coverage Report (raw YAML)", "source": yaml_source, "type": "text/yaml"},
                        {"name": "Coverage Summary (text)", "source": text_source, "type": "text/plain"},
                    ],
                }
                (allure_results_dir / f"{coverage_uuid}-result.json").write_text(json.dumps(result))

                print(f"✓ Coverage Summary written into: {allure_results_dir}")
        
    except Exception as e:
        print(f"\n✗ Error generating coverage report: {e}")
        import traceback
        traceback.print_exc()
