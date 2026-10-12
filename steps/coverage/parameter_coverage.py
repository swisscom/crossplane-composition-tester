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

"""Parameter coverage tracking for Crossplane compositions."""

import logging
from pathlib import Path
from typing import Set, Optional, Iterable
import yaml
import re

from steps.coverage.models import ParameterCoverage

logger = logging.getLogger("xplane-composition-tester logger")


def extract_parameters_from_schema(schema: dict, prefix: str = "") -> Set[str]:
    """
    Recursively extract parameter paths from OpenAPI schema.
    
    Args:
        schema: OpenAPI schema dict
        prefix: Current path prefix
        
    Returns:
        Set of parameter paths (e.g., "serviceAccountName", "policiesARN")
    """
    parameters = set()
    
    if not isinstance(schema, dict):
        return parameters
    
    # Get properties if they exist
    properties = schema.get('properties', {})
    
    for prop_name, prop_schema in properties.items():
        # Build the parameter path
        if prefix:
            param_path = f"{prefix}.{prop_name}"
        else:
            param_path = prop_name
        
        # Add this parameter
        parameters.add(param_path)
        
        # If this property has nested properties, recurse
        if isinstance(prop_schema, dict) and 'properties' in prop_schema:
            nested = extract_parameters_from_schema(prop_schema, param_path)
            parameters.update(nested)
        
        # Handle array items with object schemas
        if isinstance(prop_schema, dict) and prop_schema.get('type') == 'array':
            items = prop_schema.get('items', {})
            if isinstance(items, dict) and 'properties' in items:
                nested = extract_parameters_from_schema(items, param_path)
                parameters.update(nested)
    
    return parameters


def extract_parameters_from_definition(definition_file: Path) -> Set[str]:
    """
    Extract all possible parameters from a Crossplane XRD definition file.
    
    Args:
        definition_file: Path to definition.yaml file
        
    Returns:
        Set of parameter names that can be configured
    """
    parameters = set()
    
    try:
        with open(definition_file, 'r') as f:
            definition = yaml.safe_load(f)
        
        # Navigate to the schema: spec.versions[].schema.openAPIV3Schema
        versions = definition.get('spec', {}).get('versions', [])
        
        for version in versions:
            schema = version.get('schema', {}).get('openAPIV3Schema', {})
            
            # We're interested in spec parameters
            spec_schema = schema.get('properties', {}).get('spec', {})
            
            # Extract all parameter paths from spec
            spec_params = extract_parameters_from_schema(spec_schema)
            parameters.update(spec_params)
        
        logger.info(f"Extracted {len(parameters)} parameters from {definition_file.name}")
        
    except Exception as e:
        logger.error(f"Error extracting parameters from {definition_file}: {e}")
    
    return parameters


def extract_parameters_from_claim(claim_file: Path) -> Set[str]:
    """
    Extract parameters that are actually set in a claim file.
    
    Args:
        claim_file: Path to claim YAML file
        
    Returns:
        Set of parameter names that are set in the claim
    """
    parameters = set()
    
    try:
        with open(claim_file, 'r') as f:
            # Use safe_load_all to handle multi-document YAML files
            documents = list(yaml.safe_load_all(f))
        
        # Process each document in the file
        for claim in documents:
            if not isinstance(claim, dict):
                continue
            
            # Get spec section
            spec = claim.get('spec', {})
            
            # Recursively collect all keys set in spec
            def collect_keys(obj, prefix=""):
                if not isinstance(obj, dict):
                    return
                
                for key, value in obj.items():
                    if prefix:
                        param_path = f"{prefix}.{key}"
                    else:
                        param_path = key
                    
                    parameters.add(param_path)
                    
                    # Recurse into nested objects
                    if isinstance(value, dict):
                        collect_keys(value, param_path)
                    elif isinstance(value, list):
                        # For lists, just mark the parameter itself
                        # We don't track individual array elements
                        pass
            
            collect_keys(spec)
        
    except Exception as e:
        logger.warning(f"Error extracting parameters from {claim_file}: {e}")
    
    return parameters


def extract_parameters_from_feature(feature_file: Path) -> Set[str]:
    r"""
    Extract parameters used in a feature file (from Gherkin tables).
    
    This scans for patterns like:
        | param name       | param value      |
        | spec.policiesARN | \list policyArn1 |
    
    Args:
        feature_file: Path to .feature file
        
    Returns:
        Set of parameter names used in the feature
    """
    parameters = set()
    
    try:
        with open(feature_file, 'r') as f:
            content = f.read()
        
        # Look for table rows with "param name" column
        # Pattern: | some.parameter.path | value |
        lines = content.split('\n')
        in_table = False
        param_name_col_idx = None
        
        for line in lines:
            line = line.strip()
            
            # Check if this is a table header with "param name"
            if '|' in line and 'param name' in line.lower():
                in_table = True
                # Find which column has "param name"
                cols = [col.strip() for col in line.split('|')]
                try:
                    param_name_col_idx = cols.index('param name')
                except ValueError:
                    # Try case-insensitive
                    for idx, col in enumerate(cols):
                        if col.lower() == 'param name':
                            param_name_col_idx = idx
                            break
                continue
            
            # If we're in a table and this is a data row
            if in_table and '|' in line and not line.startswith('#'):
                if line.strip() == '|':  # Empty table row
                    in_table = False
                    param_name_col_idx = None
                    continue
                
                cols = [col.strip() for col in line.split('|')]
                if param_name_col_idx is not None and len(cols) > param_name_col_idx:
                    param_name = cols[param_name_col_idx]
                    # Skip if it's the header row again or empty
                    if param_name and param_name.lower() != 'param name':
                        # Remove "spec." prefix if present to match definition parameters
                        if param_name.startswith('spec.'):
                            param_name = param_name[5:]
                        parameters.add(param_name)
            elif in_table and not ('|' in line):
                # End of table
                in_table = False
                param_name_col_idx = None
        
    except Exception as e:
        logger.warning(f"Error extracting parameters from feature {feature_file}: {e}")
    
    return parameters


def _iter_feature_files(feature_dir: Path, feature_files: Optional[Iterable[Path]] = None) -> Iterable[Path]:
    if feature_files is None:
        return feature_dir.glob("*.feature")
    return feature_files


def _extract_referenced_claim_files(feature_files: Iterable[Path], resources_dir: Path) -> Set[Path]:
    """Find claim yaml files referenced by the provided feature files."""
    referenced = set()
    claim_re = re.compile(r'input claim\s+([a-zA-Z0-9\-_./]+\.ya?ml)', re.IGNORECASE)

    for feature_file in feature_files:
        try:
            content = feature_file.read_text()
        except Exception:
            continue

        for match in claim_re.findall(content):
            # Features typically reference claims relative to the resources/ folder.
            candidate = (resources_dir / match).resolve() if resources_dir.exists() else Path(match)
            # If the match already includes 'resources/', handle it gracefully.
            if candidate.exists():
                referenced.add(candidate)
                continue

            alt = (resources_dir / Path(match).name).resolve()
            if alt.exists():
                referenced.add(alt)

    return referenced


def extract_parameters_from_claims(
    composition_dir: Path,
    feature_dir: Path,
    feature_files: Optional[Iterable[Path]] = None
) -> Set[str]:
    """
    Extract all parameters used in claims and feature files for a composition.
    
    Args:
        composition_dir: Directory containing composition files (pkg/<name>/)
        feature_dir: Directory containing test files (composition-tests/<name>/)
        
    Returns:
        Set of all parameters used in tests
    """
    used_parameters = set()
    
    # Check for claim files in resources subdirectory
    resources_dir = feature_dir / "resources"
    if resources_dir.exists():
        claim_files_to_scan: Iterable[Path]
        if feature_files is None:
            claim_files_to_scan = resources_dir.glob("*.yaml")
        else:
            claim_files_to_scan = _extract_referenced_claim_files(_iter_feature_files(feature_dir, feature_files), resources_dir)

        for claim_file in claim_files_to_scan:
            # Skip "observed" files - these are test fixtures with observed state, not actual claims
            if "observed" in claim_file.name.lower():
                logger.debug(f"Skipping observed file: {claim_file.name}")
                continue
            
            params = extract_parameters_from_claim(claim_file)
            used_parameters.update(params)
            logger.debug(f"Found {len(params)} parameters in {claim_file.name}")
    
    # Check feature files for parameter usage in tables
    for feature_file in _iter_feature_files(feature_dir, feature_files):
        params = extract_parameters_from_feature(feature_file)
        used_parameters.update(params)
        logger.debug(f"Found {len(params)} parameters in {feature_file.name}")
    
    logger.info(f"Total {len(used_parameters)} unique parameters used in tests")
    
    return used_parameters


def calculate_parameter_coverage(
    composition_name: str,
    definition_file: Path,
    composition_dir: Path,
    feature_dir: Path,
    feature_files: Optional[Iterable[Path]] = None
) -> ParameterCoverage:
    """
    Calculate parameter coverage for a composition.
    
    Args:
        composition_name: Name of the composition
        definition_file: Path to definition.yaml
        composition_dir: Directory with composition files
        feature_dir: Directory with test files
        
    Returns:
        ParameterCoverage object with coverage metrics
    """
    # Extract all possible parameters from definition
    all_parameters = extract_parameters_from_definition(definition_file)
    
    # Extract parameters actually used in tests
    used_parameters = extract_parameters_from_claims(composition_dir, feature_dir, feature_files=feature_files)
    
    # Calculate coverage
    covered = all_parameters.intersection(used_parameters)
    uncovered = all_parameters - used_parameters
    
    coverage = ParameterCoverage(
        composition_name=composition_name,
        parameters_total=len(all_parameters),
        parameters_covered=len(covered),
        covered_parameters=sorted(list(covered)),
        uncovered_parameters=sorted(list(uncovered))
    )
    
    logger.info(
        f"Parameter coverage for {composition_name}: "
        f"{coverage.parameters_covered}/{coverage.parameters_total} "
        f"({coverage.coverage_percentage:.1f}%)"
    )
    
    return coverage