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

"""Unit tests for coverage models."""

import unittest
import json
import yaml

from steps.coverage.models import (
    ParameterCoverage,
    TemplateFunctionCoverage,
    CoverageReport,
)


class TestParameterCoverage(unittest.TestCase):
    """Test ParameterCoverage model."""
    
    def test_coverage_percentage_with_parameters(self):
        """Test coverage percentage calculation."""
        coverage = ParameterCoverage(
            composition_name="test-composition",
            parameters_total=10,
            parameters_covered=7,
            covered_parameters=["param1", "param2", "param3"],
            uncovered_parameters=["param4", "param5"]
        )
        
        self.assertEqual(coverage.coverage_percentage, 70.0)
    
    def test_coverage_percentage_zero_parameters(self):
        """Test coverage percentage when no parameters exist."""
        coverage = ParameterCoverage(
            composition_name="test-composition",
            parameters_total=0,
            parameters_covered=0
        )
        
        self.assertEqual(coverage.coverage_percentage, 0.0)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        coverage = ParameterCoverage(
            composition_name="test-composition",
            parameters_total=10,
            parameters_covered=5,
            covered_parameters=["param1"],
            uncovered_parameters=["param2"]
        )
        
        result = coverage.to_dict()
        
        self.assertIn('composition_name', result)
        self.assertIn('parameters_total', result)
        self.assertIn('coverage_percentage', result)
        self.assertEqual(result['coverage_percentage'], 50.0)


class TestTemplateFunctionCoverage(unittest.TestCase):
    """Test TemplateFunctionCoverage model."""
    
    def test_coverage_percentage(self):
        """Test coverage percentage calculation."""
        coverage = TemplateFunctionCoverage(
            functions_total=100,
            functions_used=25,
            used_functions={"func1": 5, "func2": 10},
            unused_functions=["func3", "func4"]
        )
        
        self.assertEqual(coverage.coverage_percentage, 25.0)
    
    def test_coverage_percentage_zero_functions(self):
        """Test coverage percentage when no functions exist."""
        coverage = TemplateFunctionCoverage(
            functions_total=0,
            functions_used=0
        )
        
        self.assertEqual(coverage.coverage_percentage, 0.0)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        coverage = TemplateFunctionCoverage(
            functions_total=50,
            functions_used=10,
            used_functions={"func1": 3},
            unused_functions=["func2"]
        )
        
        result = coverage.to_dict()
        
        self.assertIn('functions_total', result)
        self.assertIn('functions_used', result)
        self.assertIn('coverage_percentage', result)
        self.assertEqual(result['coverage_percentage'], 20.0)


class TestCoverageReport(unittest.TestCase):
    """Test CoverageReport model."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        param_cov = ParameterCoverage(
            composition_name="test",
            parameters_total=5,
            parameters_covered=3
        )
        
        func_cov = TemplateFunctionCoverage(
            functions_total=20,
            functions_used=10
        )
        
        report = CoverageReport(
            parameter_coverage_by_composition={"test": param_cov},
            template_function_coverage=func_cov
        )
        
        result = report.to_dict()
        
        self.assertIn('parameter_coverage_by_composition', result)
        self.assertIn('template_function_coverage', result)
        self.assertIn('test', result['parameter_coverage_by_composition'])
    
    def test_to_json(self):
        """Test JSON serialization."""
        report = CoverageReport()
        json_str = report.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
    
    def test_to_yaml(self):
        """Test YAML serialization."""
        report = CoverageReport()
        yaml_str = report.to_yaml()
        
        # Should be valid YAML
        parsed = yaml.safe_load(yaml_str)
        self.assertIsInstance(parsed, dict)


if __name__ == '__main__':
    unittest.main()
