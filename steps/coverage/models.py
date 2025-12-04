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

"""Data models for coverage reporting."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List
import json
import yaml


@dataclass
class ParameterCoverage:
    """Coverage information for parameters in a composition."""
    
    composition_name: str
    parameters_total: int = 0
    parameters_covered: int = 0
    covered_parameters: List[str] = field(default_factory=list)
    uncovered_parameters: List[str] = field(default_factory=list)
    
    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage percentage."""
        if self.parameters_total == 0:
            return 0.0
        return (self.parameters_covered / self.parameters_total) * 100.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary with computed fields."""
        result = asdict(self)
        result['coverage_percentage'] = round(self.coverage_percentage, 2)
        return result


@dataclass
class TemplateFunctionCoverage:
    """Coverage information for Go template functions."""
    
    functions_total: int = 0
    functions_used: int = 0
    used_functions: Dict[str, int] = field(default_factory=dict)
    unused_functions: List[str] = field(default_factory=list)
    
    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage percentage."""
        if self.functions_total == 0:
            return 0.0
        return (self.functions_used / self.functions_total) * 100.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary with computed fields."""
        result = asdict(self)
        result['coverage_percentage'] = round(self.coverage_percentage, 2)
        return result


@dataclass
class CoverageReport:
    """Complete coverage report for compositions."""
    
    parameter_coverage_by_composition: Dict[str, ParameterCoverage] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'parameter_coverage_by_composition': {
                name: coverage.to_dict() 
                for name, coverage in self.parameter_coverage_by_composition.items()
            }
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def to_yaml(self) -> str:
        """Convert to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)
