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

"""Unit tests for parameter coverage tracking."""

import unittest
import tempfile
import yaml
from pathlib import Path

from steps.coverage.parameter_coverage import (
    extract_parameters_from_schema,
    extract_parameters_from_definition,
    extract_parameters_from_claim,
    extract_parameters_from_feature,
    calculate_parameter_coverage,
)


class TestParameterExtraction(unittest.TestCase):
    """Test parameter extraction functions."""
    
    def test_extract_parameters_from_simple_schema(self):
        """Test extracting parameters from a simple schema."""
        schema = {
            'properties': {
                'param1': {'type': 'string'},
                'param2': {'type': 'integer'}
            }
        }
        
        params = extract_parameters_from_schema(schema)
        
        self.assertEqual(len(params), 2)
        self.assertIn('param1', params)
        self.assertIn('param2', params)
    
    def test_extract_parameters_from_nested_schema(self):
        """Test extracting parameters from nested schema."""
        schema = {
            'properties': {
                'level1': {
                    'type': 'object',
                    'properties': {
                        'level2': {'type': 'string'}
                    }
                }
            }
        }
        
        params = extract_parameters_from_schema(schema)
        
        self.assertIn('level1', params)
        self.assertIn('level1.level2', params)
    
    def test_extract_parameters_from_array_schema(self):
        """Test extracting parameters from array with object items."""
        schema = {
            'properties': {
                'items': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'itemProp': {'type': 'string'}
                        }
                    }
                }
            }
        }
        
        params = extract_parameters_from_schema(schema)
        
        self.assertIn('items', params)
        self.assertIn('items.itemProp', params)
    
    def test_extract_parameters_from_definition_file(self):
        """Test extracting parameters from a definition YAML file."""
        definition_content = """
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: test
spec:
  versions:
    - name: v1alpha1
      served: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                serviceAccountName:
                  type: string
                serviceAccountNamespace:
                  type: string
                policiesARN:
                  type: array
                  items:
                    type: string
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(definition_content)
            temp_file = Path(f.name)
        
        try:
            params = extract_parameters_from_definition(temp_file)
            
            self.assertGreater(len(params), 0)
            self.assertIn('serviceAccountName', params)
            self.assertIn('serviceAccountNamespace', params)
            self.assertIn('policiesARN', params)
        finally:
            temp_file.unlink()
    
    def test_extract_parameters_from_claim_file(self):
        """Test extracting parameters from a claim YAML file."""
        claim_content = """
apiVersion: example.com/v1alpha1
kind: SrvAccount
metadata:
  name: test-sa
spec:
  serviceAccountName: test-sa
  serviceAccountNamespace: default
  policiesARN:
    - arn:aws:iam::123:policy/test
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(claim_content)
            temp_file = Path(f.name)
        
        try:
            params = extract_parameters_from_claim(temp_file)
            
            self.assertGreater(len(params), 0)
            self.assertIn('serviceAccountName', params)
            self.assertIn('serviceAccountNamespace', params)
            self.assertIn('policiesARN', params)
        finally:
            temp_file.unlink()
    
    def test_extract_parameters_from_feature_file(self):
        """Test extracting parameters from a Gherkin feature file."""
        feature_content = """
Feature: Test feature
  
  Scenario: Test scenario
    Given input claim is changed with parameters
      | param name       | param value      |
      | spec.policiesARN | \\list policyArn1 |
      | spec.timeout     | 300              |
    
    Then check that resource has parameters
      | param name    | param value |
      | metadata.name | test-name   |
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.feature', delete=False) as f:
            f.write(feature_content)
            temp_file = Path(f.name)
        
        try:
            params = extract_parameters_from_feature(temp_file)
            
            self.assertGreater(len(params), 0)
            # Should extract without "spec." prefix
            self.assertIn('policiesARN', params)
            self.assertIn('timeout', params)
        finally:
            temp_file.unlink()


class TestParameterCoverageCalculation(unittest.TestCase):
    """Test parameter coverage calculation."""
    
    def setUp(self):
        """Set up temporary directories for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create directory structure
        self.pkg_dir = self.temp_path / "pkg" / "test-composition"
        self.test_dir = self.temp_path / "composition-tests" / "test-composition"
        self.resources_dir = self.test_dir / "resources"
        
        self.pkg_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)
        self.resources_dir.mkdir(parents=True)
    
    def tearDown(self):
        """Clean up temporary directories."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_calculate_parameter_coverage(self):
        """Test calculating parameter coverage."""
        # Create definition file
        definition_content = """
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: test
spec:
  versions:
    - name: v1alpha1
      served: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                param1:
                  type: string
                param2:
                  type: string
                param3:
                  type: string
"""
        definition_file = self.pkg_dir / "definition.yaml"
        with open(definition_file, 'w') as f:
            f.write(definition_content)
        
        # Create claim file (only uses param1)
        claim_content = """
apiVersion: example.com/v1alpha1
kind: Test
spec:
  param1: value1
"""
        claim_file = self.resources_dir / "claim.yaml"
        with open(claim_file, 'w') as f:
            f.write(claim_content)
        
        # Calculate coverage
        coverage = calculate_parameter_coverage(
            composition_name="test-composition",
            definition_file=definition_file,
            composition_dir=self.pkg_dir,
            feature_dir=self.test_dir
        )
        
        # Should have 3 total parameters
        self.assertEqual(coverage.parameters_total, 3)
        
        # Should have 1 covered parameter
        self.assertEqual(coverage.parameters_covered, 1)
        self.assertIn('param1', coverage.covered_parameters)
        
        # Should have 2 uncovered parameters
        self.assertEqual(len(coverage.uncovered_parameters), 2)
        self.assertIn('param2', coverage.uncovered_parameters)
        self.assertIn('param3', coverage.uncovered_parameters)
        
        # Coverage should be ~33.33%
        self.assertAlmostEqual(coverage.coverage_percentage, 33.33, places=1)


if __name__ == '__main__':
    unittest.main()
