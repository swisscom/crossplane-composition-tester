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

"""Managed resource coverage tracking for Crossplane compositions."""

import logging
from pathlib import Path
from typing import Set, Optional, Iterable
import yaml
import re

from steps.coverage.models import ManagedResourceCoverage

logger = logging.getLogger("xplane-composition-tester logger")


def extract_resources_from_composition(composition_file: Path) -> Set[str]:
    """
    Extract all managed resources from a composition file.
    
    Handles both traditional compositions and pipeline-based compositions.
    For pipeline compositions, parses Go templates to find resource definitions.
    Also extracts resource name mappings from context setup (e.g., metadataNames, resourceNames).
    
    Args:
        composition_file: Path to composition.yaml file
        
    Returns:
        Set of resource names (logical names that tests use, after mapping resolution)
    """
    resources = set()
    resource_name_mapping = {}  # Maps internal name -> test-facing name
    
    try:
        with open(composition_file, 'r') as f:
            composition = yaml.safe_load(f)
        
        # Check if it's a traditional composition (spec.resources)
        if 'spec' in composition and 'resources' in composition['spec']:
            for resource in composition['spec']['resources']:
                # Get name from metadata.name or annotations
                if 'name' in resource:
                    resources.add(resource['name'])
                elif 'metadata' in resource.get('base', {}):
                    name = resource['base']['metadata'].get('name')
                    if name:
                        resources.add(name)
        
        # Check if it's a pipeline composition (spec.pipeline)
        if 'spec' in composition and 'pipeline' in composition['spec']:
            for step in composition['spec']['pipeline']:
                if 'input' not in step:
                    continue
                
                input_config = step['input']
                
                # Look for inline templates with resource definitions
                if input_config.get('kind') == 'GoTemplate':
                    template_content = ""
                    
                    if 'inline' in input_config and 'template' in input_config['inline']:
                        template_content = input_config['inline']['template']
                    elif 'source' in input_config and input_config['source'] == 'Inline':
                        template_content = input_config.get('inline', {}).get('template', '')
                    
                    if template_content:
                        # Extract resource name mappings from context setup
                        # Pattern: resourceNames:\n  resource: s3Bucket\n  resourcePolicy: saPolicy
                        # or metadataNames:\n  resource: s3Bucket
                        mapping_pattern = r'(?:resourceNames|metadataNames):\s*\n((?:\s+[a-zA-Z0-9\-_]+:\s*[a-zA-Z0-9\-_]+\s*\n?)+)'
                        mapping_matches = re.findall(mapping_pattern, template_content)
                        
                        for mapping_block in mapping_matches:
                            # Parse each line: "  key: value"
                            for line in mapping_block.strip().split('\n'):
                                match = re.match(r'\s*([a-zA-Z0-9\-_]+):\s*([a-zA-Z0-9\-_]+)', line)
                                if match:
                                    internal_name, external_name = match.groups()
                                    resource_name_mapping[internal_name] = external_name
                        
                        # Extract resource names from gotemplating.fn.crossplane.io/composition-resource-name annotations
                        pattern = r'gotemplating\.fn\.crossplane\.io/composition-resource-name:\s*["\']?([a-zA-Z0-9\-_\.]+)["\']?'
                        matches = re.findall(pattern, template_content)
                        resources.update(matches)
                        
                        # Also look for {{.context.resourceNames.XXX}} patterns
                        context_pattern = r'\{\{\.context\.resourceNames\.([a-zA-Z0-9\-_]+)\}\}'
                        context_matches = re.findall(context_pattern, template_content)
                        resources.update(context_matches)
                        
                        # Look for {{ setResourceNameAnnotation .context.resourceNames.XXX }} patterns
                        set_annotation_pattern = r'setResourceNameAnnotation\s+\.context\.resourceNames\.([a-zA-Z0-9\-_]+)'
                        set_annotation_matches = re.findall(set_annotation_pattern, template_content)
                        resources.update(set_annotation_matches)
        
        # Apply resource name mapping to get test-facing names
        if resource_name_mapping:
            mapped_resources = set()
            for resource in resources:
                # Use mapped name if available, otherwise keep original
                mapped_resources.add(resource_name_mapping.get(resource, resource))
            resources = mapped_resources
            
            logger.debug(f"Applied resource name mapping: {resource_name_mapping}")
        
        logger.info(f"Extracted {len(resources)} managed resources from {composition_file.name}")
        logger.debug(f"Resources found: {sorted(resources)}")
        
    except Exception as e:
        logger.error(f"Error extracting resources from {composition_file}: {e}")
    
    return resources


def extract_resources_from_tests(feature_dir: Path, feature_files: Optional[Iterable[Path]] = None) -> Set[str]:
    """
    Extract resource names that are tested in feature files.
    
    Looks for patterns like:
        - "check that resource XXX has parameters"
        - "check that X resources are provisioning and they are"
        - "change observed resource XXX"
    
    Args:
        feature_dir: Directory containing test .feature files
        
    Returns:
        Set of resource names mentioned in tests
    """
    tested_resources = set()
    
    try:
        files_to_scan: Iterable[Path]
        if feature_files is None:
            files_to_scan = feature_dir.glob("*.feature")
        else:
            files_to_scan = feature_files

        for feature_file in files_to_scan:
            with open(feature_file, 'r') as f:
                content = f.read()
            
            # Pattern 1: "check that resource XXX has parameters"
            pattern1 = r'check that resource\s+([a-zA-Z0-9\-_]+)\s+has parameters'
            matches1 = re.findall(pattern1, content, re.IGNORECASE)
            tested_resources.update(matches1)
            
            # Pattern 2: Table with resource names (| resource-name |)
            lines = content.split('\n')
            in_resource_table = False
            resource_col_idx = None
            
            for line in lines:
                line = line.strip()
                
                # Check if this is a resource table header
                if '|' in line and 'resource-name' in line.lower():
                    in_resource_table = True
                    cols = [col.strip() for col in line.split('|')]
                    try:
                        resource_col_idx = cols.index('resource-name')
                    except ValueError:
                        for idx, col in enumerate(cols):
                            if col.lower() == 'resource-name':
                                resource_col_idx = idx
                                break
                    continue
                
                # If we're in a resource table, extract resource names
                if in_resource_table and '|' in line and not line.startswith('#'):
                    if line.strip() == '|':
                        in_resource_table = False
                        resource_col_idx = None
                        continue
                    
                    cols = [col.strip() for col in line.split('|')]
                    if resource_col_idx is not None and len(cols) > resource_col_idx:
                        resource_name = cols[resource_col_idx]
                        if resource_name and resource_name.lower() != 'resource-name':
                            tested_resources.add(resource_name)
                elif in_resource_table and not ('|' in line):
                    in_resource_table = False
                    resource_col_idx = None
            
            # Pattern 3: "change observed resource XXX"
            pattern3 = r'change observed resource\s+([a-zA-Z0-9\-_]+)'
            matches3 = re.findall(pattern3, content, re.IGNORECASE)
            tested_resources.update(matches3)
            
            # Pattern 4: getComposedResource references in templates (if testing with actual templates)
            pattern4 = r'getComposedResource.*?["\']([a-zA-Z0-9\-_]+)["\']'
            matches4 = re.findall(pattern4, content)
            tested_resources.update(matches4)
            
            logger.debug(f"Found {len(tested_resources)} resources in {feature_file.name}")
    
    except Exception as e:
        logger.warning(f"Error extracting resources from tests in {feature_dir}: {e}")
    
    return tested_resources


def calculate_managed_resource_coverage(
    composition_name: str,
    composition_file: Path,
    feature_dir: Path,
    feature_files: Optional[Iterable[Path]] = None
) -> ManagedResourceCoverage:
    """
    Calculate managed resource coverage for a composition.
    
    Args:
        composition_name: Name of the composition
        composition_file: Path to composition.yaml
        feature_dir: Directory with test files
        
    Returns:
        ManagedResourceCoverage object with coverage metrics
    """
    # Extract all resources from composition
    all_resources = extract_resources_from_composition(composition_file)
    
    # Extract resources tested
    tested_resources = extract_resources_from_tests(feature_dir, feature_files=feature_files)
    
    # Calculate coverage
    covered = all_resources.intersection(tested_resources)
    uncovered = all_resources - tested_resources
    
    coverage = ManagedResourceCoverage(
        composition_name=composition_name,
        resources_total=len(all_resources),
        resources_covered=len(covered),
        covered_resources=sorted(list(covered)),
        uncovered_resources=sorted(list(uncovered))
    )
    
    logger.info(
        f"Managed resource coverage for {composition_name}: "
        f"{coverage.resources_covered}/{coverage.resources_total} "
        f"({coverage.coverage_percentage:.1f}%)"
    )
    
    return coverage
