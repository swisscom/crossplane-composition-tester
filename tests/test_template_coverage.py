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

"""Unit tests for template function coverage tracking."""

import unittest
import tempfile
from pathlib import Path

from steps.coverage.template_coverage import (
    TemplateFunctionTracker,
    extract_template_functions_from_composition,
    GO_TEMPLATE_FUNCTIONS,
)


class TestTemplateFunctionTracker(unittest.TestCase):
    """Test TemplateFunctionTracker class."""
    
    def setUp(self):
        """Set up a fresh tracker for each test."""
        self.tracker = TemplateFunctionTracker()
    
    def test_tracker_initialization(self):
        """Test tracker is initialized correctly."""
        self.assertFalse(self.tracker.enabled)
        self.assertEqual(len(self.tracker.used_functions), 0)
        self.assertGreater(len(self.tracker.available_functions), 0)
    
    def test_enable_disable(self):
        """Test enabling and disabling tracking."""
        self.assertFalse(self.tracker.enabled)
        
        self.tracker.enable()
        self.assertTrue(self.tracker.enabled)
        
        self.tracker.disable()
        self.assertFalse(self.tracker.enabled)
    
    def test_record_function_usage(self):
        """Test recording function usage."""
        self.tracker.enable()
        
        # Record a function
        self.tracker.record_function_usage('index')
        
        self.assertEqual(self.tracker.used_functions.get('index'), 1)
        
        # Record same function again
        self.tracker.record_function_usage('index')
        
        self.assertEqual(self.tracker.used_functions.get('index'), 2)
    
    def test_record_function_when_disabled(self):
        """Test that recording doesn't work when disabled."""
        self.tracker.disable()
        
        self.tracker.record_function_usage('index')
        
        self.assertEqual(len(self.tracker.used_functions), 0)
    
    def test_get_coverage(self):
        """Test getting coverage report."""
        self.tracker.enable()
        
        # Record some functions
        self.tracker.record_function_usage('index')
        self.tracker.record_function_usage('upper')
        self.tracker.record_function_usage('index')
        
        coverage = self.tracker.get_coverage()
        
        self.assertEqual(coverage.functions_used, 2)
        self.assertIn('index', coverage.used_functions)
        self.assertIn('upper', coverage.used_functions)
        self.assertEqual(coverage.used_functions['index'], 2)
        self.assertEqual(coverage.used_functions['upper'], 1)
        
        # Should have many unused functions
        self.assertGreater(len(coverage.unused_functions), 0)
        self.assertNotIn('index', coverage.unused_functions)
        self.assertNotIn('upper', coverage.unused_functions)
    
    def test_reset(self):
        """Test resetting tracker."""
        self.tracker.enable()
        self.tracker.record_function_usage('index')
        
        self.assertEqual(len(self.tracker.used_functions), 1)
        
        self.tracker.reset()
        
        self.assertEqual(len(self.tracker.used_functions), 0)


class TestExtractTemplateFunctions(unittest.TestCase):
    """Test extracting template functions from compositions."""
    
    def test_extract_functions_from_composition(self):
        """Test extracting functions from a composition file."""
        composition_content = """
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: test
spec:
  mode: Pipeline
  pipeline:
  - step: test-step
    functionRef:
      name: function-go-templating
    input:
      apiVersion: gotemplating.fn.crossplane.io/v1beta1
      kind: GoTemplate
      source: Inline
      inline:
        template: |-
          {{ $var := index .context "key" }}
          {{ $upper := upper "hello" }}
          {{ $result := printf "%s-%s" $var $upper }}
          ---
          apiVersion: v1
          kind: Resource
          metadata:
            name: {{ lower $result }}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(composition_content)
            temp_file = Path(f.name)
        
        try:
            functions = extract_template_functions_from_composition(temp_file)
            
            # Should find these functions
            self.assertIn('index', functions)
            self.assertIn('upper', functions)
            self.assertIn('printf', functions)
            self.assertIn('lower', functions)
            
        finally:
            temp_file.unlink()
    
    def test_extract_functions_from_piped_template(self):
        """Test extracting functions from piped template expressions."""
        composition_content = """
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
spec:
  mode: Pipeline
  pipeline:
  - step: test
    input:
      apiVersion: gotemplating.fn.crossplane.io/v1beta1
      kind: GoTemplate
      inline:
        template: |-
          {{ .value | upper | trim }}
          {{ .list | first | lower }}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(composition_content)
            temp_file = Path(f.name)
        
        try:
            functions = extract_template_functions_from_composition(temp_file)
            
            # Should find piped functions
            self.assertIn('upper', functions)
            self.assertIn('trim', functions)
            self.assertIn('first', functions)
            self.assertIn('lower', functions)
            
        finally:
            temp_file.unlink()
    
    def test_extract_functions_with_no_template(self):
        """Test extraction from composition without inline templates."""
        composition_content = """
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
spec:
  mode: Resources
  resources:
  - name: test
    base:
      apiVersion: v1
      kind: Resource
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(composition_content)
            temp_file = Path(f.name)
        
        try:
            functions = extract_template_functions_from_composition(temp_file)
            
            # Should find no functions
            self.assertEqual(len(functions), 0)
            
        finally:
            temp_file.unlink()


class TestGoTemplateFunctions(unittest.TestCase):
    """Test the GO_TEMPLATE_FUNCTIONS constant."""
    
    def test_common_functions_present(self):
        """Test that common Go template functions are in the list."""
        common_functions = [
            'index', 'printf', 'upper', 'lower', 'trim',
            'split', 'join', 'default', 'toJson', 'list',
            'dict', 'add', 'sub', 'mul', 'div'
        ]
        
        for func in common_functions:
            self.assertIn(func, GO_TEMPLATE_FUNCTIONS, f"Function '{func}' should be in GO_TEMPLATE_FUNCTIONS")


if __name__ == '__main__':
    unittest.main()
