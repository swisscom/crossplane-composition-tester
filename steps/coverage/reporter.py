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
from typing import Dict
import json

from steps.coverage.models import CoverageReport, ParameterCoverage
from steps.coverage.parameter_coverage import calculate_parameter_coverage

logger = logging.getLogger("xplane-composition-tester logger")


def generate_coverage_report(test_root: Path) -> CoverageReport:
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
    
    if not pkg_dir.exists():
        logger.warning(f"No pkg directory found at {pkg_dir}")
        return report
    
    if not composition_tests_dir.exists():
        logger.warning(f"No composition-tests directory found at {composition_tests_dir}")
        return report
    
    # Iterate through each composition directory
    for composition_dir in pkg_dir.iterdir():
        if not composition_dir.is_dir():
            continue
        
        composition_name = composition_dir.name
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
        
        # Calculate parameter coverage for this composition
        param_coverage = calculate_parameter_coverage(
            composition_name=composition_name,
            definition_file=definition_file,
            composition_dir=composition_dir,
            feature_dir=feature_dir
        )
        
        report.parameter_coverage_by_composition[composition_name] = param_coverage
    
    return report


def print_coverage_summary(report: CoverageReport):
    """
    Print a human-readable coverage summary to console.
    
    Args:
        report: CoverageReport to print
    """
    print("\n" + "=" * 80)
    print("CROSSPLANE COMPOSITION COVERAGE REPORT")
    print("=" * 80)
    
    # Parameter coverage section
    print("\n📋 PARAMETER COVERAGE BY COMPOSITION")
    print("-" * 80)
    
    if not report.parameter_coverage_by_composition:
        print("  No compositions found")
    else:
        for comp_name, coverage in sorted(report.parameter_coverage_by_composition.items()):
            print(f"\n  Composition: {comp_name}")
            print(f"    Total Parameters:   {coverage.parameters_total}")
            print(f"    Covered Parameters: {coverage.parameters_covered}")
            print(f"    Coverage:           {coverage.coverage_percentage:.1f}%")
            
            if coverage.covered_parameters:
                print(f"    ✓ Covered: {', '.join(coverage.covered_parameters[:5])}", end="")
                if len(coverage.covered_parameters) > 5:
                    print(f" ... and {len(coverage.covered_parameters) - 5} more")
                else:
                    print()
            
            if coverage.uncovered_parameters:
                print(f"    ✗ Uncovered: {', '.join(coverage.uncovered_parameters[:5])}", end="")
                if len(coverage.uncovered_parameters) > 5:
                    print(f" ... and {len(coverage.uncovered_parameters) - 5} more")
                else:
                    print()
    
    print("\n" + "=" * 80)


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
