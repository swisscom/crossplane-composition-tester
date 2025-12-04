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
    CoverageReport,
)
from steps.coverage.parameter_coverage import (
    extract_parameters_from_definition,
    extract_parameters_from_claims,
    calculate_parameter_coverage,
)
from steps.coverage.reporter import (
    generate_coverage_report,
    print_coverage_summary,
    save_coverage_report,
)

__all__ = [
    "ParameterCoverage",
    "CoverageReport",
    "extract_parameters_from_definition",
    "extract_parameters_from_claims",
    "calculate_parameter_coverage",
    "generate_coverage_report",
    "print_coverage_summary",
    "save_coverage_report",
]
