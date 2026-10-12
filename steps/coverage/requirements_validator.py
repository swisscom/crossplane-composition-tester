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

"""Validator for the composition coverage requirements (minimum coverage thresholds)."""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List
from steps.coverage.models import (
    CoverageReport,
    ParameterCoverage,
    ManagedResourceCoverage,
    ResourceParameterCoverage,
    StatementCoverage
)

logger = logging.getLogger("xplane-composition-tester logger")


class CoverageLevel(Enum):
    """Coverage requirement levels."""
    MINIMAL = "minimal"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class CoverageRequirement:
    """Coverage requirement specification."""
    name: str
    minimal: float
    medium: float
    high: float
    unit: str = "%"


@dataclass
class RequirementValidationResult:
    """Result of validating coverage against requirements."""
    composition_name: str
    level_achieved: CoverageLevel
    requirements_met: Dict[str, bool]
    coverage_values: Dict[str, float]
    details: List[str]


# Minimum coverage thresholds per requirement level
REQUIREMENTS = {
    "managed_resources": CoverageRequirement(
        name="Managed Resources Coverage",
        minimal=100.0,
        medium=100.0,
        high=100.0
    ),
    "resource_parameters_avg": CoverageRequirement(
        name="Average Parameters per Resource",
        minimal=60.0,
        medium=80.0,
        high=100.0
    ),
    "composition_statements": CoverageRequirement(
        name="Composition Statements Coverage",
        minimal=70.0,
        medium=90.0,
        high=100.0
    ),
    "definition_parameters": CoverageRequirement(
        name="Definition Parameters Coverage",
        minimal=70.0,
        medium=100.0,
        high=100.0
    )
}


def calculate_average_resource_parameter_coverage(
    resource_coverage: Dict[str, ResourceParameterCoverage]
) -> float:
    """
    Calculate average parameter coverage across all resources.
    
    Args:
        resource_coverage: Dictionary of resource name to ResourceParameterCoverage
        
    Returns:
        Average coverage percentage across all resources
    """
    if not resource_coverage:
        return 0.0
    
    total_coverage = sum(cov.coverage_percentage for cov in resource_coverage.values())
    return total_coverage / len(resource_coverage)


def validate_composition_requirements(
    composition_name: str,
    param_coverage: ParameterCoverage,
    resource_coverage: ManagedResourceCoverage,
    resource_param_coverage: Dict[str, ResourceParameterCoverage],
    statement_coverage: StatementCoverage
) -> RequirementValidationResult:
    """
    Validate a composition's coverage against the coverage requirements.
    
    Args:
        composition_name: Name of the composition
        param_coverage: Parameter coverage for definition.yaml
        resource_coverage: Managed resource coverage
        resource_param_coverage: Per-resource parameter coverage
        statement_coverage: Statement coverage
        
    Returns:
        RequirementValidationResult with validation details
    """
    coverage_values = {
        "managed_resources": resource_coverage.coverage_percentage,
        "resource_parameters_avg": calculate_average_resource_parameter_coverage(resource_param_coverage),
        "composition_statements": statement_coverage.coverage_percentage,
        "definition_parameters": param_coverage.coverage_percentage
    }
    
    # Check each level (HIGH, MEDIUM, MINIMAL)
    level_checks = {
        CoverageLevel.HIGH: {},
        CoverageLevel.MEDIUM: {},
        CoverageLevel.MINIMAL: {}
    }
    
    for req_key, requirement in REQUIREMENTS.items():
        actual_value = coverage_values.get(req_key, 0.0)
        
        level_checks[CoverageLevel.HIGH][req_key] = actual_value >= requirement.high
        level_checks[CoverageLevel.MEDIUM][req_key] = actual_value >= requirement.medium
        level_checks[CoverageLevel.MINIMAL][req_key] = actual_value >= requirement.minimal
    
    # Determine achieved level
    level_achieved = None
    if all(level_checks[CoverageLevel.HIGH].values()):
        level_achieved = CoverageLevel.HIGH
    elif all(level_checks[CoverageLevel.MEDIUM].values()):
        level_achieved = CoverageLevel.MEDIUM
    elif all(level_checks[CoverageLevel.MINIMAL].values()):
        level_achieved = CoverageLevel.MINIMAL
    else:
        level_achieved = None
    
    # Generate detailed feedback
    details = []
    for req_key, requirement in REQUIREMENTS.items():
        actual = coverage_values[req_key]
        
        status = "✓" if level_achieved and all(level_checks[level_achieved].values()) else "✗"
        
        if level_achieved == CoverageLevel.HIGH:
            target = requirement.high
            level_str = "HIGH"
        elif level_achieved == CoverageLevel.MEDIUM:
            target = requirement.medium
            level_str = "MEDIUM"
        elif level_achieved == CoverageLevel.MINIMAL:
            target = requirement.minimal
            level_str = "MINIMAL"
        else:
            # Show what's needed for minimal
            target = requirement.minimal
            level_str = "MINIMAL (NOT MET)"
            status = "✗"
        
        detail = f"{status} {requirement.name}: {actual:.1f}% (target: {target:.1f}% for {level_str})"
        details.append(detail)
        
        # Add guidance if not meeting requirements
        if actual < requirement.minimal:
            gap = requirement.minimal - actual
            details.append(f"  ⚠ Need {gap:.1f}% more to reach MINIMAL level")
        elif actual < requirement.medium and level_achieved != CoverageLevel.HIGH:
            gap = requirement.medium - actual
            details.append(f"  ℹ Need {gap:.1f}% more to reach MEDIUM level")
        elif actual < requirement.high:
            gap = requirement.high - actual
            details.append(f"  ℹ Need {gap:.1f}% more to reach HIGH level")
    
    requirements_met = level_checks.get(level_achieved, {}) if level_achieved else {}
    
    result = RequirementValidationResult(
        composition_name=composition_name,
        level_achieved=level_achieved,
        requirements_met=requirements_met,
        coverage_values=coverage_values,
        details=details
    )
    
    return result


def validate_all_compositions(report: CoverageReport) -> Dict[str, RequirementValidationResult]:
    """
    Validate all compositions in a coverage report against requirements.
    
    Args:
        report: Complete coverage report
        
    Returns:
        Dictionary mapping composition name to validation result
    """
    results = {}
    
    # Get all composition names
    composition_names = set(
        list(report.parameter_coverage_by_composition.keys()) +
        list(report.managed_resource_coverage_by_composition.keys()) +
        list(report.statement_coverage_by_composition.keys())
    )
    
    for comp_name in composition_names:
        param_cov = report.parameter_coverage_by_composition.get(comp_name)
        resource_cov = report.managed_resource_coverage_by_composition.get(comp_name)
        resource_param_cov = report.resource_parameter_coverage_by_composition.get(comp_name, {})
        statement_cov = report.statement_coverage_by_composition.get(comp_name)
        
        # Skip if essential data is missing
        if not param_cov or not resource_cov or not statement_cov:
            logger.warning(f"Incomplete coverage data for {comp_name}, skipping validation")
            continue
        
        result = validate_composition_requirements(
            comp_name,
            param_cov,
            resource_cov,
            resource_param_cov,
            statement_cov
        )
        
        results[comp_name] = result
    
    return results


def print_validation_summary(results: Dict[str, RequirementValidationResult]):
    """
    Print a summary of requirement validation results.
    
    Args:
        results: Dictionary of validation results by composition
    """
    print("\n" + "=" * 80)
    print("COVERAGE REQUIREMENTS VALIDATION")
    print("=" * 80)
    
    if not results:
        print("  No compositions validated")
        return
    
    # Summary by level
    level_counts = {
        CoverageLevel.HIGH: 0,
        CoverageLevel.MEDIUM: 0,
        CoverageLevel.MINIMAL: 0,
        None: 0
    }
    
    for result in results.values():
        level_counts[result.level_achieved] = level_counts.get(result.level_achieved, 0) + 1
    
    print("\n📊 SUMMARY BY LEVEL")
    print("-" * 80)
    print(f"  🏆 HIGH level:    {level_counts[CoverageLevel.HIGH]} compositions")
    print(f"  📈 MEDIUM level:  {level_counts[CoverageLevel.MEDIUM]} compositions")
    print(f"  📋 MINIMAL level: {level_counts[CoverageLevel.MINIMAL]} compositions")
    print(f"  ❌ Below minimal: {level_counts[None]} compositions")
    
    # Detailed results per composition
    print("\n📝 DETAILED RESULTS")
    print("-" * 80)
    
    for comp_name, result in sorted(results.items()):
        level_str = result.level_achieved.value.upper() if result.level_achieved else "BELOW MINIMAL"
        level_emoji = {
            CoverageLevel.HIGH: "🏆",
            CoverageLevel.MEDIUM: "📈",
            CoverageLevel.MINIMAL: "📋",
            None: "❌"
        }[result.level_achieved]
        
        print(f"\n  Composition: {comp_name}")
        print(f"  Level: {level_emoji} {level_str}")
        print(f"  Coverage Metrics:")
        
        for detail in result.details:
            print(f"    {detail}")
    
    print("\n" + "=" * 80)
