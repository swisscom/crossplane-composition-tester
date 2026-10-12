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

"""Statement coverage tracking for Crossplane composition logic."""

import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Iterable
import yaml
import re

from steps.coverage.models import StatementCoverage

logger = logging.getLogger("xplane-composition-tester logger")


def extract_statements_from_composition(composition_file: Path) -> Tuple[Set[str], Dict[str, List[str]]]:
    """
    Extract logical statements and conditional paths from a composition.
    
    Analyzes:
    - Conditional blocks ({{- if }}, {{- with }})
    - Template variables ({{- $variable := }})
    - Function calls (getCompositeResource, ternary, etc.)
    - Loops ({{- range }})
    
    Args:
        composition_file: Path to composition.yaml
        
    Returns:
        Tuple of (statements, conditional_paths)
        - statements: Set of unique statement identifiers
        - conditional_paths: Dict mapping condition to list of resources it affects
    """
    statements = set()
    conditional_paths = {}
    
    try:
        with open(composition_file, 'r') as f:
            composition = yaml.safe_load(f)
        
        # Only analyze pipeline compositions with Go templates
        if 'spec' not in composition or 'pipeline' not in composition['spec']:
            logger.debug(f"No pipeline found in {composition_file.name}, skipping statement analysis")
            return statements, conditional_paths
        
        for step_idx, step in enumerate(composition['spec']['pipeline']):
            step_name = step.get('step', f'step-{step_idx}')
            
            if 'input' not in step:
                continue
            
            input_config = step['input']
            
            if input_config.get('kind') != 'GoTemplate':
                continue
            
            template_content = ""
            if 'inline' in input_config and 'template' in input_config['inline']:
                template_content = input_config['inline']['template']
            
            if not template_content:
                continue
            
            # Extract different types of statements
            
            # 1. Variable declarations
            var_declarations = re.findall(r'\{\{-?\s*\$([a-zA-Z0-9_]+)\s*:=', template_content)
            for var in var_declarations:
                statements.add(f"variable_declaration:${var}")
            
            # 2. Conditional blocks - if statements
            if_conditions = re.findall(r'\{\{-?\s*if\s+(.+?)\s*\}\}', template_content)
            for idx, condition in enumerate(if_conditions):
                condition_clean = _clean_condition(condition)
                statement_id = f"conditional:if:{step_name}:{idx}:{condition_clean[:50]}"
                statements.add(statement_id)
                
                # Try to find which resources this affects
                affected_resources = _find_affected_resources(template_content, condition)
                if affected_resources:
                    conditional_paths[statement_id] = affected_resources
            
            # 3. With blocks
            with_conditions = re.findall(r'\{\{-?\s*with\s+(.+?)\s*\}\}', template_content)
            for idx, condition in enumerate(with_conditions):
                condition_clean = _clean_condition(condition)
                statement_id = f"conditional:with:{step_name}:{idx}:{condition_clean[:50]}"
                statements.add(statement_id)
                
                affected_resources = _find_affected_resources(template_content, condition)
                if affected_resources:
                    conditional_paths[statement_id] = affected_resources
            
            # 4. Ternary operators
            ternary_ops = re.findall(r'([^\s]+)\s*\|\s*ternary\s+([^\s]+)\s+([^\s]+)', template_content)
            for idx, (condition, true_val, false_val) in enumerate(ternary_ops):
                statement_id = f"ternary:{step_name}:{idx}:{condition[:30]}"
                statements.add(statement_id)
            
            # 5. Function calls
            function_patterns = [
                (r'getCompositeResource', 'function:getCompositeResource'),
                (r'getComposedResource', 'function:getComposedResource'),
                (r'getResourceCondition', 'function:getResourceCondition'),
                (r'setResourceNameAnnotation', 'function:setResourceNameAnnotation'),
                (r'toYaml', 'function:toYaml'),
                (r'index\s+', 'function:index'),
                (r'printf', 'function:printf'),
            ]
            
            for pattern, func_name in function_patterns:
                matches = re.findall(pattern, template_content)
                if matches:
                    statement_id = f"{func_name}:{step_name}"
                    statements.add(statement_id)
            
            # 6. Range loops
            range_loops = re.findall(r'\{\{-?\s*range\s+(.+?)\s*\}\}', template_content)
            for idx, range_expr in enumerate(range_loops):
                statement_id = f"loop:range:{step_name}:{idx}:{range_expr[:30]}"
                statements.add(statement_id)
            
            # 7. Else statements
            else_count = len(re.findall(r'\{\{-?\s*else\s*\}\}', template_content))
            for idx in range(else_count):
                statements.add(f"conditional:else:{step_name}:{idx}")
        
        logger.info(f"Extracted {len(statements)} statements from {composition_file.name}")
        logger.debug(f"Conditional paths: {len(conditional_paths)}")
        
    except Exception as e:
        logger.error(f"Error extracting statements from {composition_file}: {e}")
    
    return statements, conditional_paths


def _clean_condition(condition: str) -> str:
    """Clean and normalize a condition string for use as identifier."""
    # Remove extra whitespace
    condition = ' '.join(condition.split())
    # Remove template syntax
    condition = condition.replace('{{', '').replace('}}', '')
    # Limit length
    if len(condition) > 50:
        condition = condition[:47] + '...'
    return condition


def _find_affected_resources(template_content: str, condition: str) -> List[str]:
    """
    Find which resources are affected by a conditional block.
    
    Looks for resource definitions that appear after the condition
    in the template.
    """
    resources = []
    
    # Find the position of the condition
    condition_pos = template_content.find(condition)
    if condition_pos == -1:
        return resources
    
    # Look for resource annotations in the block following this condition
    # Find the next {{- end }} to determine the block scope
    end_pos = template_content.find('{{- end }}', condition_pos)
    if end_pos == -1:
        end_pos = len(template_content)
    
    block = template_content[condition_pos:end_pos]
    
    # Extract resource names from annotations
    resource_names = re.findall(
        r'gotemplating\.fn\.crossplane\.io/composition-resource-name:\s*["\']?([a-zA-Z0-9\-_\.]+)',
        block
    )
    resources.extend(resource_names)
    
    # Also check for context.resourceNames references
    context_resources = re.findall(r'\{\{\.context\.resourceNames\.([a-zA-Z0-9\-_]+)\}\}', block)
    resources.extend(context_resources)
    
    return list(set(resources))  # Deduplicate


def extract_tested_statements_from_features(feature_dir: Path, feature_files: Optional[Iterable[Path]] = None) -> Set[str]:
    """
    Extract statements that are tested by analyzing test scenarios.
    
    A statement is considered tested if:
    - Tests verify resources created by conditional blocks
    - Tests change observed state to trigger different paths
    - Tests validate resource presence/absence based on conditions
    
    Args:
        feature_dir: Directory containing test .feature files
        
    Returns:
        Set of statement identifiers that are tested
    """
    tested_statements = set()
    
    try:
        files_to_scan: Iterable[Path]
        if feature_files is None:
            files_to_scan = feature_dir.glob("*.feature")
        else:
            files_to_scan = feature_files

        for feature_file in files_to_scan:
            with open(feature_file, 'r') as f:
                content = f.read()
            
            # Look for patterns indicating conditional path testing
            
            # 1. "change observed resource" indicates testing conditional paths
            if 'change observed resource' in content:
                tested_statements.add('tested:conditional_paths')
            
            # 2. Multiple render steps indicate testing different states
            render_count = len(re.findall(r'crossplane renders the composition', content))
            if render_count > 1:
                tested_statements.add('tested:multiple_renders')
                # This suggests conditional logic is being tested
                tested_statements.add('tested:state_transitions')
            
            # 3. Checking resource counts suggests conditional resource creation
            resource_count_checks = re.findall(
                r'check that (\d+) resources? (?:is|are) provisioning',
                content
            )
            if len(set(resource_count_checks)) > 1:
                tested_statements.add('tested:conditional_resource_creation')
            
            # 4. Status changes (READY, NOT READY) trigger conditional blocks
            if 'with status READY' in content or 'with status NOT READY' in content:
                tested_statements.add('tested:status_conditionals')
            
            # 5. Testing with different parameter values
            param_variations = re.findall(r'input claim ([a-zA-Z0-9\-_]+\.yaml)', content)
            if len(set(param_variations)) > 1:
                tested_statements.add('tested:parameter_variations')
            
            # 6. Explicit conditional testing patterns
            if 'serviceAccountName' in content:
                tested_statements.add('tested:serviceAccountName_conditional')
            
            logger.debug(f"Found {len(tested_statements)} tested statement patterns in {feature_file.name}")
    
    except Exception as e:
        logger.warning(f"Error extracting tested statements from {feature_dir}: {e}")
    
    return tested_statements


def calculate_statement_coverage(
    composition_name: str,
    composition_file: Path,
    feature_dir: Path,
    feature_files: Optional[Iterable[Path]] = None
) -> StatementCoverage:
    """
    Calculate statement coverage for a composition.
    
    Args:
        composition_name: Name of the composition
        composition_file: Path to composition.yaml
        feature_dir: Directory with test files
        
    Returns:
        StatementCoverage object with metrics
    """
    # Extract all statements and conditional paths
    all_statements, conditional_paths = extract_statements_from_composition(composition_file)
    
    # Extract tested statement patterns
    tested_patterns = extract_tested_statements_from_features(feature_dir, feature_files=feature_files)
    
    # For now, we'll use a heuristic approach:
    # If we have evidence of testing conditional paths, count relevant statements as covered
    
    covered_statements = set()
    
    # If we see conditional path testing, mark conditional statements as tested
    if 'tested:conditional_paths' in tested_patterns or 'tested:state_transitions' in tested_patterns:
        for stmt in all_statements:
            if 'conditional:' in stmt:
                covered_statements.add(stmt)
    
    # If we see status conditionals tested, mark getResourceCondition as tested
    if 'tested:status_conditionals' in tested_patterns:
        for stmt in all_statements:
            if 'getResourceCondition' in stmt:
                covered_statements.add(stmt)
    
    # If we see parameter variations, mark ternary and variable declarations as tested
    if 'tested:parameter_variations' in tested_patterns:
        for stmt in all_statements:
            if 'ternary:' in stmt or 'variable_declaration:' in stmt:
                covered_statements.add(stmt)
    
    # Always mark commonly used functions as tested if any resources are tested
    if tested_patterns:
        for stmt in all_statements:
            if any(func in stmt for func in ['function:toYaml', 'function:printf', 'function:index']):
                covered_statements.add(stmt)
    
    # Calculate covered conditional paths
    covered_paths = []
    for path_id, resources in conditional_paths.items():
        if path_id in covered_statements:
            covered_paths.append(path_id)
    
    coverage = StatementCoverage(
        composition_name=composition_name,
        total_statements=len(all_statements),
        covered_statements=len(covered_statements),
        conditional_paths=list(conditional_paths.keys()),
        covered_paths=covered_paths,
        tested_patterns=sorted(list(tested_patterns))
    )
    
    logger.info(
        f"Statement coverage for {composition_name}: "
        f"{coverage.covered_statements}/{coverage.total_statements} "
        f"({coverage.coverage_percentage:.1f}%)"
    )
    
    return coverage
