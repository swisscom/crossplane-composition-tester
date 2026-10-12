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

"""Per-resource parameter coverage tracking for Crossplane compositions."""

import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Iterable
import yaml
import re

from steps.coverage.models import ResourceParameterCoverage

logger = logging.getLogger("xplane-composition-tester logger")


def extract_parameters_from_resource_template(template_content: str, resource_name: str) -> Set[str]:
    """
    Extract parameters for a specific resource from a Go template.
    
    This parses the YAML structure within the template to find all
    parameters (fields) that are set for a given resource.
    
    Args:
        template_content: The Go template content as string
        resource_name: Name of the resource to extract parameters for
        
    Returns:
        Set of parameter paths (e.g., "spec.deletionPolicy", "spec.forProvider.locationConstraint")
    """
    parameters = set()
    
    try:
        
        # Split template by --- to get individual resources
        resource_docs = template_content.split('---')
        
        for doc in resource_docs:
            if not doc.strip():
                continue
            
            # Check if this document is for our resource
            if resource_name in doc or f'.resourceNames.{resource_name}' in doc or f'composition-resource-name: {resource_name}' in doc:
                # Try to parse as YAML to extract structure
                # But Go template syntax will break YAML parsing, so we use regex
                
                # Extract parameters from spec.* paths
                spec_params = re.findall(r'^\s*(spec(?:\.[a-zA-Z0-9_\[\]]+)+):\s*', doc, re.MULTILINE)
                parameters.update(spec_params)
                
                # Extract from apiVersion, kind, metadata
                if re.search(r'^\s*apiVersion:', doc, re.MULTILINE):
                    parameters.add('apiVersion')
                if re.search(r'^\s*kind:', doc, re.MULTILINE):
                    parameters.add('kind')
                
                metadata_params = re.findall(r'^\s*(metadata\.[a-zA-Z0-9_]+):', doc, re.MULTILINE)
                parameters.update(metadata_params)
                
                # Extract nested parameters more carefully
                # Look for patterns like "  forProvider:" followed by nested fields
                lines = doc.split('\n')
                current_path = []
                indent_stack = []
                
                for line in lines:
                    if not line.strip() or line.strip().startswith('#'):
                        continue
                    
                    # Skip Go template directives
                    if '{{' in line or '}}' in line:
                        continue
                    
                    # Get indentation level
                    indent = len(line) - len(line.lstrip())
                    
                    # Extract key
                    match = re.match(r'\s*([a-zA-Z0-9_\[\]]+):\s*', line)
                    if match:
                        key = match.group(1)
                        
                        # Adjust path based on indentation
                        while indent_stack and indent <= indent_stack[-1]:
                            indent_stack.pop()
                            if current_path:
                                current_path.pop()
                        
                        # Add to current path
                        current_path.append(key)
                        indent_stack.append(indent)
                        
                        # Record the full path
                        full_path = '.'.join(current_path)
                        parameters.add(full_path)
    
    except Exception as e:
        logger.debug(f"Error extracting parameters for resource {resource_name}: {e}")
    
    return parameters


def extract_resource_parameters_from_composition(
    composition_file: Path,
    resource_name: str
) -> Set[str]:
    """
    Extract all parameters for a specific managed resource from composition.
    
    Args:
        composition_file: Path to composition.yaml
        resource_name: Name of the resource to analyze
        
    Returns:
        Set of parameter paths defined for this resource
    """
    parameters = set()
    
    try:
        with open(composition_file, 'r') as f:
            composition = yaml.safe_load(f)
        
        # Handle traditional compositions
        if 'spec' in composition and 'resources' in composition['spec']:
            for resource in composition['spec']['resources']:
                res_name = resource.get('name', '')
                if res_name == resource_name:
                    # Extract parameters from base
                    if 'base' in resource:
                        params = _extract_params_from_dict(resource['base'])
                        parameters.update(params)
                    
                    # Extract from patches
                    if 'patches' in resource:
                        for patch in resource['patches']:
                            if 'toFieldPath' in patch:
                                parameters.add(patch['toFieldPath'])
        
        # Handle pipeline compositions
        if 'spec' in composition and 'pipeline' in composition['spec']:
            for step in composition['spec']['pipeline']:
                if 'input' not in step:
                    continue
                
                input_config = step['input']
                
                if input_config.get('kind') == 'GoTemplate':
                    template_content = ""
                    
                    if 'inline' in input_config and 'template' in input_config['inline']:
                        template_content = input_config['inline']['template']
                    
                    if template_content:
                        params = extract_parameters_from_resource_template(template_content, resource_name)
                        parameters.update(params)
        
        logger.debug(f"Extracted {len(parameters)} parameters for resource {resource_name}")
        
    except Exception as e:
        logger.error(f"Error extracting resource parameters from {composition_file}: {e}")
    
    return parameters


def _extract_params_from_dict(data: dict, prefix: str = "") -> Set[str]:
    """Recursively extract parameter paths from a dictionary."""
    parameters = set()
    
    if not isinstance(data, dict):
        return parameters
    
    for key, value in data.items():
        if prefix:
            param_path = f"{prefix}.{key}"
        else:
            param_path = key
        
        parameters.add(param_path)
        
        if isinstance(value, dict):
            nested = _extract_params_from_dict(value, param_path)
            parameters.update(nested)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # For arrays of objects, extract from first element as template
            nested = _extract_params_from_dict(value[0], param_path)
            parameters.update(nested)
    
    return parameters


def extract_tested_resource_parameters_from_features(
    feature_dir: Path,
    resource_name: str,
    feature_files: Optional[Iterable[Path]] = None
) -> Set[str]:
    """
    Extract parameters that are tested for a specific resource in feature files.
    
    Looks for "check that resource XXX has parameters" scenarios.
    
    Args:
        feature_dir: Directory containing test .feature files
        resource_name: Name of the resource to check
        
    Returns:
        Set of parameter paths tested for this resource
    """
    tested_parameters = set()
    
    try:
        files_to_scan: Iterable[Path]
        if feature_files is None:
            files_to_scan = feature_dir.glob("*.feature")
        else:
            files_to_scan = feature_files

        for feature_file in files_to_scan:
            with open(feature_file, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            in_resource_test = False
            in_param_table = False
            param_name_col_idx = None
            key_prefix = ""
            
            for line in lines:
                line_stripped = line.strip()
                
                # Check if we're starting a test for this resource
                if f'check that resource {resource_name} has parameters' in line_stripped.lower():
                    in_resource_test = True
                    in_param_table = False
                    # 'has parameters with key prefix <prefix>': table params are relative to the prefix
                    prefix_match = re.search(r'with key prefix\s+(\S+)', line_stripped)
                    key_prefix = f"{prefix_match.group(1)}." if prefix_match else ""
                    continue
                
                # If we're in a resource test, look for parameter tables
                if in_resource_test:
                    # Check for table header
                    if '|' in line_stripped and 'param name' in line_stripped.lower():
                        in_param_table = True
                        cols = [col.strip() for col in line_stripped.split('|')]
                        try:
                            param_name_col_idx = cols.index('param name')
                        except ValueError:
                            for idx, col in enumerate(cols):
                                if col.lower() == 'param name':
                                    param_name_col_idx = idx
                                    break
                        continue
                    
                    # Extract parameters from table rows
                    if in_param_table and '|' in line_stripped and not line_stripped.startswith('#'):
                        if line_stripped == '|':
                            in_param_table = False
                            in_resource_test = False
                            param_name_col_idx = None
                            continue
                        
                        cols = [col.strip() for col in line_stripped.split('|')]
                        if param_name_col_idx is not None and len(cols) > param_name_col_idx:
                            param_name = cols[param_name_col_idx]
                            if param_name and param_name.lower() != 'param name':
                                tested_parameters.add(key_prefix + param_name)
                    
                    # Check if we've moved to a different section
                    elif in_param_table and not ('|' in line_stripped):
                        in_param_table = False
                        in_resource_test = False
                        param_name_col_idx = None

            
            logger.debug(f"Found {len(tested_parameters)} tested parameters for {resource_name} in {feature_file.name}")
    
    except Exception as e:
        logger.warning(f"Error extracting tested parameters for {resource_name} from {feature_dir}: {e}")
    
    return tested_parameters


def calculate_resource_parameter_coverage(
    composition_name: str,
    composition_file: Path,
    feature_dir: Path,
    resource_name: str,
    feature_files: Optional[Iterable[Path]] = None
) -> ResourceParameterCoverage:
    """
    Calculate parameter coverage for a specific managed resource.
    
    Args:
        composition_name: Name of the composition
        composition_file: Path to composition.yaml
        feature_dir: Directory with test files
        resource_name: Name of the managed resource
        
    Returns:
        ResourceParameterCoverage object with metrics
    """
    # Extract all parameters for this resource from composition
    all_parameters = extract_resource_parameters_from_composition(composition_file, resource_name)
    
    # Extract tested parameters
    tested_parameters = extract_tested_resource_parameters_from_features(
        feature_dir,
        resource_name,
        feature_files=feature_files
    )
    
    # Calculate coverage
    covered = all_parameters.intersection(tested_parameters)
    uncovered = all_parameters - tested_parameters
    
    coverage = ResourceParameterCoverage(
        composition_name=composition_name,
        resource_name=resource_name,
        parameters_total=len(all_parameters),
        parameters_covered=len(covered),
        covered_parameters=sorted(list(covered)),
        uncovered_parameters=sorted(list(uncovered))
    )
    
    logger.info(
        f"Parameter coverage for resource {resource_name} in {composition_name}: "
        f"{coverage.parameters_covered}/{coverage.parameters_total} "
        f"({coverage.coverage_percentage:.1f}%)"
    )
    
    return coverage


def calculate_all_resources_parameter_coverage(
    composition_name: str,
    composition_file: Path,
    feature_dir: Path,
    resource_names: List[str],
    feature_files: Optional[Iterable[Path]] = None
) -> Dict[str, ResourceParameterCoverage]:
    """
    Calculate parameter coverage for all managed resources.
    
    Args:
        composition_name: Name of the composition
        composition_file: Path to composition.yaml
        feature_dir: Directory with test files
        resource_names: List of resource names to analyze
        
    Returns:
        Dictionary mapping resource name to ResourceParameterCoverage
    """
    coverage_by_resource = {}
    
    for resource_name in resource_names:
        coverage = calculate_resource_parameter_coverage(
            composition_name,
            composition_file,
            feature_dir,
            resource_name,
            feature_files=feature_files
        )
        coverage_by_resource[resource_name] = coverage
    
    return coverage_by_resource
