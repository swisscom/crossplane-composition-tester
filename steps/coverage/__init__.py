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

"""Coverage module for Crossplane compositions."""

from steps.coverage.models import (
    ParameterCoverage,
    ManagedResourceCoverage,
    ResourceParameterCoverage,
    StatementCoverage,
    CoverageReport,
)
from steps.coverage.parameter_coverage import (
    extract_parameters_from_definition,
    extract_parameters_from_claims,
    calculate_parameter_coverage,
)
from steps.coverage.managed_resource_coverage import (
    extract_resources_from_composition,
    extract_resources_from_tests,
    calculate_managed_resource_coverage,
)
from steps.coverage.resource_parameter_coverage import (
    calculate_resource_parameter_coverage,
    calculate_all_resources_parameter_coverage,
)
from steps.coverage.statement_coverage import (
    extract_statements_from_composition,
    calculate_statement_coverage,
)
from steps.coverage.requirements_validator import (
    CoverageLevel,
    validate_composition_requirements,
    validate_all_compositions,
    print_validation_summary,
)
from steps.coverage.reporter import (
    generate_coverage_report,
    print_coverage_summary,
    save_coverage_report,
)

__all__ = [
    # Models
    "ParameterCoverage",
    "ManagedResourceCoverage",
    "ResourceParameterCoverage",
    "StatementCoverage",
    "CoverageReport",
    # Parameter coverage
    "extract_parameters_from_definition",
    "extract_parameters_from_claims",
    "calculate_parameter_coverage",
    # Managed resource coverage
    "extract_resources_from_composition",
    "extract_resources_from_tests",
    "calculate_managed_resource_coverage",
    # Resource parameter coverage
    "calculate_resource_parameter_coverage",
    "calculate_all_resources_parameter_coverage",
    # Statement coverage
    "extract_statements_from_composition",
    "calculate_statement_coverage",
    # Requirements validation
    "CoverageLevel",
    "validate_composition_requirements",
    "validate_all_compositions",
    "print_validation_summary",
    # Reporting
    "generate_coverage_report",
    "print_coverage_summary",
    "save_coverage_report",
]