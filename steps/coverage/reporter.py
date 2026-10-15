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

"""Coverage report generation and formatting."""

import logging
from pathlib import Path
from typing import Optional, Set

from steps.coverage.models import CoverageReport
from steps.coverage.parameter_coverage import calculate_parameter_coverage
from steps.coverage.managed_resource_coverage import calculate_managed_resource_coverage
from steps.coverage.resource_parameter_coverage import calculate_all_resources_parameter_coverage
from steps.coverage.statement_coverage import calculate_statement_coverage
from steps.coverage.requirements_validator import validate_all_compositions, print_validation_summary

logger = logging.getLogger("xplane-composition-tester logger")


def generate_coverage_report(test_root: Path, executed_feature_files: Optional[Set[Path]] = None) -> CoverageReport:
    """
    Generate a complete coverage report for all compositions in the test directory.
    
    Args:
        test_root: Root directory containing composition-tests/ and pkg/ subdirectories
        
    Returns:
        CoverageReport object with all coverage metrics
    """
    report = CoverageReport()
    
    # Find all compositions
    pkg_dir = test_root / "pkg"
    composition_tests_dir = test_root / "composition-tests"

    # Resolve to handle symlinked roots (e.g. ".target_project" -> real repo path).
    try:
        composition_tests_dir_resolved = composition_tests_dir.resolve()
    except Exception:
        composition_tests_dir_resolved = composition_tests_dir
    
    if not pkg_dir.exists():
        logger.warning(f"No pkg directory found at {pkg_dir}")
        return report
    
    if not composition_tests_dir.exists():
        logger.warning(f"No composition-tests directory found at {composition_tests_dir}")
        return report
    
    executed_feature_files_normalized: Optional[Set[Path]] = None
    executed_compositions: Optional[Set[str]] = None

    if executed_feature_files:
        executed_feature_files_normalized = set()
        for p in executed_feature_files:
            try:
                executed_feature_files_normalized.add(Path(p).resolve())
            except Exception:
                executed_feature_files_normalized.add(Path(p))

        # Map executed feature files to composition directories under composition-tests/
        executed_compositions = set()
        for feature_path in executed_feature_files_normalized:
            try:
                rel = feature_path.relative_to(composition_tests_dir_resolved)
            except Exception:
                continue

            # Expected layout: composition-tests/<composition-name>/*.feature
            if len(rel.parts) >= 2:
                executed_compositions.add(rel.parts[0])

        logger.info(
            f"Coverage will be computed for executed compositions only: {sorted(executed_compositions)}"
        )

    # Iterate through each composition directory
    for composition_dir in pkg_dir.iterdir():
        if not composition_dir.is_dir():
            continue
        
        composition_name = composition_dir.name

        if executed_compositions is not None and composition_name not in executed_compositions:
            continue
        definition_file = composition_dir / "definition.yaml"
        composition_file = composition_dir / "composition.yaml"
        
        if not definition_file.exists():
            logger.warning(f"No definition.yaml found for {composition_name}, skipping")
            continue
        
        if not composition_file.exists():
            logger.warning(f"No composition.yaml found for {composition_name}, skipping")
            continue
        
        # Find corresponding test directory
        feature_dir = composition_tests_dir / composition_name
        if not feature_dir.exists():
            logger.warning(f"No test directory found for {composition_name}, skipping")
            continue

        feature_files_for_composition: Optional[Set[Path]] = None
        if executed_feature_files_normalized is not None:
            feature_files_for_composition = set()
            try:
                feature_dir_resolved = feature_dir.resolve()
            except Exception:
                feature_dir_resolved = feature_dir

            for feature_path in executed_feature_files_normalized:
                try:
                    feature_path.relative_to(feature_dir_resolved)
                except Exception:
                    continue
                if feature_path.suffix == ".feature":
                    feature_files_for_composition.add(feature_path)

            if not feature_files_for_composition:
                # No executed features for this composition.
                continue
        
        logger.info(f"Analyzing coverage for {composition_name}...")
        
        # 1. Calculate parameter coverage (definition.yaml parameters)
        param_coverage = calculate_parameter_coverage(
            composition_name=composition_name,
            definition_file=definition_file,
            composition_dir=composition_dir,
            feature_dir=feature_dir,
            feature_files=feature_files_for_composition
        )
        report.parameter_coverage_by_composition[composition_name] = param_coverage
        
        # 2. Calculate managed resource coverage
        resource_coverage = calculate_managed_resource_coverage(
            composition_name=composition_name,
            composition_file=composition_file,
            feature_dir=feature_dir,
            feature_files=feature_files_for_composition
        )
        report.managed_resource_coverage_by_composition[composition_name] = resource_coverage
        
        # 3. Calculate per-resource parameter coverage
        if resource_coverage.covered_resources:
            resource_param_coverage = calculate_all_resources_parameter_coverage(
                composition_name=composition_name,
                composition_file=composition_file,
                feature_dir=feature_dir,
                resource_names=list(resource_coverage.covered_resources),
                feature_files=feature_files_for_composition
            )
            report.resource_parameter_coverage_by_composition[composition_name] = resource_param_coverage
        
        # 4. Calculate statement/logic coverage
        statement_coverage = calculate_statement_coverage(
            composition_name=composition_name,
            composition_file=composition_file,
            feature_dir=feature_dir,
            feature_files=feature_files_for_composition
        )
        report.statement_coverage_by_composition[composition_name] = statement_coverage
    
    return report


def print_coverage_summary(report: CoverageReport, show_validation: bool = True):
    """
    Print a human-readable coverage summary to console.
    
    Args:
        report: CoverageReport to print
        show_validation: Whether to show the coverage requirements validation results
    """
    print("\n" + "=" * 80)
    print("CROSSPLANE COMPOSITION COVERAGE REPORT")
    print("=" * 80)
    
    if not report.parameter_coverage_by_composition:
        print("  No compositions found")
        return
    
    # Get all composition names
    composition_names = sorted(set(
        list(report.parameter_coverage_by_composition.keys()) +
        list(report.managed_resource_coverage_by_composition.keys()) +
        list(report.statement_coverage_by_composition.keys())
    ))
    
    for comp_name in composition_names:
        print(f"\n{'=' * 80}")
        print(f"COMPOSITION: {comp_name}")
        print('=' * 80)
        
        # 1. Definition Parameters Coverage
        if comp_name in report.parameter_coverage_by_composition:
            coverage = report.parameter_coverage_by_composition[comp_name]
            print(f"\n📋 Definition Parameters Coverage")
            print(f"  Total:   {coverage.parameters_total}")
            print(f"  Covered: {coverage.parameters_covered}")
            print(f"  Rate:    {coverage.coverage_percentage:.1f}%")
            
            if coverage.uncovered_parameters:
                print(f"  ⚠ Uncovered ({len(coverage.uncovered_parameters)}): {', '.join(coverage.uncovered_parameters[:3])}", end="")
                if len(coverage.uncovered_parameters) > 3:
                    print(f" ... and {len(coverage.uncovered_parameters) - 3} more")
                else:
                    print()
        
        # 2. Managed Resources Coverage
        if comp_name in report.managed_resource_coverage_by_composition:
            coverage = report.managed_resource_coverage_by_composition[comp_name]
            print(f"\n🔧 Managed Resources Coverage")
            print(f"  Total:   {coverage.resources_total}")
            print(f"  Covered: {coverage.resources_covered}")
            print(f"  Rate:    {coverage.coverage_percentage:.1f}%")
            
            if coverage.covered_resources:
                print(f"  ✓ Covered: {', '.join(coverage.covered_resources)}")
            
            if coverage.uncovered_resources:
                print(f"  ✗ Uncovered: {', '.join(coverage.uncovered_resources)}")
        
        # 3. Resource Parameters Coverage
        if comp_name in report.resource_parameter_coverage_by_composition:
            resource_coverages = report.resource_parameter_coverage_by_composition[comp_name]
            print(f"\n📊 Per-Resource Parameters Coverage")
            
            if resource_coverages:
                total_params = sum(rc.parameters_total for rc in resource_coverages.values())
                covered_params = sum(rc.parameters_covered for rc in resource_coverages.values())
                avg_coverage = (covered_params / total_params * 100) if total_params > 0 else 0
                
                print(f"  Average: {avg_coverage:.1f}%")
                print(f"  Resources analyzed: {len(resource_coverages)}")
                
                for res_name, res_cov in sorted(resource_coverages.items()):
                    status = "✓" if res_cov.coverage_percentage >= 60 else "⚠"
                    print(f"    {status} {res_name}: {res_cov.coverage_percentage:.1f}% ({res_cov.parameters_covered}/{res_cov.parameters_total})")
        
        # 4. Statement Coverage
        if comp_name in report.statement_coverage_by_composition:
            coverage = report.statement_coverage_by_composition[comp_name]
            print(f"\n⚙️  Composition Statements Coverage")
            print(f"  Total:   {coverage.total_statements}")
            print(f"  Covered: {coverage.covered_statements}")
            print(f"  Rate:    {coverage.coverage_percentage:.1f}%")
            
            if coverage.conditional_paths:
                print(f"  Conditional paths: {len(coverage.covered_paths)}/{len(coverage.conditional_paths)} ({coverage.path_coverage_percentage:.1f}%)")
            
            if coverage.tested_patterns:
                print(f"  Tested patterns: {', '.join(coverage.tested_patterns[:3])}", end="")
                if len(coverage.tested_patterns) > 3:
                    print(f" ... and {len(coverage.tested_patterns) - 3} more")
                else:
                    print()
    
    print("\n" + "=" * 80)
    
    # Show validation against the coverage requirements
    if show_validation:
        validation_results = validate_all_compositions(report)
        print_validation_summary(validation_results)


def save_coverage_report(report: CoverageReport, output_path: Path, format: str = "json"):
    """
    Save coverage report to a file.
    
    Args:
        report: CoverageReport to save
        output_path: Path where to save the report
        format: Output format - "json" or "yaml"
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'w') as f:
            if format.lower() == "yaml":
                f.write(report.to_yaml())
            else:
                f.write(report.to_json())
        
        logger.info(f"Coverage report saved to {output_path}")
        print(f"\n✓ Coverage report saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving coverage report: {e}")
        print(f"\n✗ Error saving coverage report: {e}")