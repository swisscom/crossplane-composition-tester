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

from behave import fixture, use_fixture
from behave.runner import Context

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
    all_features_directory = Path(ctx.base_path).parent
    envconfig_filepath = all_features_directory / "envconfig.yaml"
    
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
    all_features_directory = Path(ctx.base_path).parent
    # Save the functions folder path in the context
    # By default, functions files are stored in the same directory as the features
    ctx.functions_folder_path = all_features_directory
    if on_ci():
        print("Running on CI!")
        ctx.on_ci = True
        # If running on CI, the default functions file is specified by the environment variable "COMPOSITION_TESTER_FUNCTIONS_FILE"
        ci_functions_file = os.environ[
            "COMPOSITION_TESTER_FUNCTIONS_FILE"
        ]  # e.g. "functions-ci.yaml"
        functions_filepath = all_features_directory / ci_functions_file
    else:
        # print("Running locally!")
        ctx.on_ci = False
        # The default functions file used for testing is "functions.yaml"
        functions_filepath = all_features_directory / "functions.yaml"

    # Save the functions file path in the context
    ctx.functions_filepath = functions_filepath


@fixture
def setup_composition_filepath(ctx: Context):
    """Setup the composition path of the current feature and save it in the context. By convention, the compositions
    directory should be in the "pkg" folder at the root of the project. Also by convention the file is named
    "composition.yaml"

    Example:
    ├── composition-tests
        ├── feature 1
            ├──
            ├── feature1.feature
        ├── feature 2
            ├──
            ├── feature2.feature
        ├── functions.yaml
    ├── pkg         # Compositions directory
        ├── feature 1
            ├── composition.yaml
        ├── feature 2
            ├── composition.yaml
    """
    # For example, "feature-1"
    feature_directory_name = ctx.base_path.name
    project_root = Path(ctx.base_path).parent.parent
    ctx.project_root = project_root
    # For example "/pkg/feature-1"
    compositions_directory = project_root / "pkg" / feature_directory_name
    ctx.compositions_directory = compositions_directory
    # For example "/pkg/feature-1/composition.yaml"
    ctx.composition_filepath = compositions_directory / "composition.yaml"

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
    # check special environment variable to determine if running locally or in CI pipeline (e.g. GITLAB_CI)
    return "COMPOSITION_TESTER_FUNCTIONS_FILE" in os.environ

def before_scenario(context: Context, scenario):
    """
    If debug mode is enabled, create an 'execution' folder for the current
    scenario inside the feature folder, and store that path in context.
    Otherwise, skip creating any new folder.
    """
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
        print("\n" + "=" * 80)
        print("COVERAGE MODE ENABLED")
        print("=" * 80)
        
        # Import coverage modules
        from steps.coverage.template_coverage import get_global_tracker, extract_all_composition_functions
        from pathlib import Path
        
        # Determine test root directory to scan for compositions
        test_root = None
        cwd = Path.cwd()
        if (cwd / "test").exists():
            test_root = cwd / "test"
        elif cwd.name == "test":
            test_root = cwd
        
        if test_root:
            print(f"Scanning compositions in: {test_root}\n")
            
            # Extract all template functions from compositions
            composition_functions = extract_all_composition_functions(test_root)
            
            # Enable template function tracking with composition functions
            tracker = get_global_tracker()
            tracker.set_composition_functions(composition_functions)
            tracker.enable()
            
            print(f"✓ Found {len(composition_functions)} template functions in compositions")
            if composition_functions:
                funcs_preview = ', '.join(sorted(composition_functions)[:10])
                if len(composition_functions) > 10:
                    funcs_preview += f" ... and {len(composition_functions) - 10} more"
                print(f"  Functions: {funcs_preview}")
        else:
            # Still enable tracking, but without pre-scanned functions
            tracker = get_global_tracker()
            tracker.enable()
            print("✓ Template function tracking enabled (no composition pre-scan)")
        
        print("✓ Parameter coverage will be calculated after tests complete")
        print("=" * 80 + "\n")


def after_all(context: Context):
    """
    Generate and display coverage report if enabled.
    """
    if not getattr(context, 'coverage_mode', False):
        return
    
    print("\n" + "=" * 80)
    print("GENERATING COVERAGE REPORT...")
    print("=" * 80 + "\n")
    
    # Import coverage modules
    from steps.coverage.reporter import generate_coverage_report, print_coverage_summary, save_coverage_report
    import allure
    
    # Determine test root directory
    # The context should have project_root set by before_feature
    test_root = None
    if hasattr(context, '_runner') and hasattr(context._runner, 'config'):
        # Get the first feature's base path to determine test root
        for feature in context._runner.features:
            if hasattr(feature, 'filename'):
                feature_path = Path(feature.filename)
                # Assume structure: test/composition-tests/<feature>/file.feature
                # So go up 2 levels to get to 'test/'
                test_root = feature_path.parent.parent.parent
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
        report = generate_coverage_report(test_root)
        
        # Print summary to console
        print_coverage_summary(report)
        
        # Save to file
        output_path = test_root.parent / "coverage-report.json"
        save_coverage_report(report, output_path, format="json")
        
        # Also save YAML version
        output_path_yaml = test_root.parent / "coverage-report.yaml"
        save_coverage_report(report, output_path_yaml, format="yaml")
        
        # Attach coverage report to Allure
        try:
            # Attach JSON report
            allure.attach.file(
                str(output_path),
                name="Coverage Report (JSON)",
                attachment_type=allure.attachment_type.JSON
            )
            
            # Attach YAML report for readability
            allure.attach.file(
                str(output_path_yaml),
                name="Coverage Report (YAML)",
                attachment_type=allure.attachment_type.TEXT
            )
            
            # Create a formatted summary for Allure
            summary_lines = ["CROSSPLANE COMPOSITION COVERAGE SUMMARY", "=" * 60, ""]
            
            for comp_name, coverage in sorted(report.parameter_coverage_by_composition.items()):
                summary_lines.append(f"Composition: {comp_name}")
                summary_lines.append(f"  Coverage: {coverage.coverage_percentage:.1f}% ({coverage.parameters_covered}/{coverage.parameters_total} parameters)")
                
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
            
            allure.attach(
                summary_text,
                name="Coverage Summary",
                attachment_type=allure.attachment_type.TEXT
            )
            
            # Create Allure environment.properties file with coverage info
            allure_reports_dir = test_root.parent / "allure_reports"
            if allure_reports_dir.exists():
                env_props_path = allure_reports_dir / "environment.properties"
                
                env_lines = []
                for comp_name, coverage in sorted(report.parameter_coverage_by_composition.items()):
                    safe_name = comp_name.replace("-", "_").replace(" ", "_")
                    env_lines.append(f"Coverage.{safe_name}={coverage.coverage_percentage:.1f}%")
                    env_lines.append(f"Coverage.{safe_name}.covered={coverage.parameters_covered}/{coverage.parameters_total}")
                
                with open(env_props_path, 'w') as f:
                    f.write("\n".join(env_lines))
                
                print(f"✓ Allure environment.properties created with coverage data")
                
                # Create a custom categories.json to show coverage as a trend
                import json
                categories_path = allure_reports_dir / "categories.json"
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
                executor_path = allure_reports_dir / "executor.json"
                executor_data = {
                    "name": "Crossplane Composition Tester",
                    "type": "behave",
                    "reportName": "Test Report with Coverage",
                    "buildName": f"Coverage Report"
                }
                with open(executor_path, 'w') as f:
                    json.dump(executor_data, f, indent=2)
            
            print("✓ Coverage reports attached to Allure")
            
        except Exception as e:
            print(f"\n⚠️  Could not attach to Allure (this is normal if allure-behave not installed): {e}")
        
    except Exception as e:
        print(f"\n✗ Error generating coverage report: {e}")
        import traceback
        traceback.print_exc()
