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

"""Analyze relationships between parameters and template functions."""

import logging
import re
from pathlib import Path
from typing import Dict, Set
import yaml

from steps.coverage.template_coverage import GO_TEMPLATE_FUNCTIONS

logger = logging.getLogger("xplane-composition-tester logger")


def extract_parameter_references_from_template(template_content: str) -> Set[str]:
    """
    Extract parameter references from a Go template.
    
    Looks for patterns like:
    - .observed.composite.resource.spec.parameterName
    - .observed.composite.resource.spec.someParam
    
    Args:
        template_content: The template string content
        
    Returns:
        Set of parameter names referenced in the template
    """
    parameters = set()
    
    # Pattern to match .observed.composite.resource.spec.PARAMETER_NAME
    # or .spec.PARAMETER_NAME variations
    patterns = [
        r'\.observed\.composite\.resource\.spec\.(\w+)',
        r'\.spec\.(\w+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, template_content)
        parameters.update(matches)
    
    return parameters


def analyze_parameter_function_usage(composition_file: Path) -> Dict[str, Set[str]]:
    """
    Analyze which template functions are used with which parameters.
    
    This looks at the entire template and identifies:
    1. Which parameters are referenced
    2. Which functions are used in the same template (implicitly tested together)
    
    The logic: If a parameter appears in a template section, all functions in that
    section are exercised when that parameter is tested.
    
    Args:
        composition_file: Path to composition.yaml
        
    Returns:
        Dict mapping parameter names to sets of function names used in same template
    """
    param_to_functions = {}
    
    try:
        with open(composition_file, 'r') as f:
            composition = yaml.safe_load(f)
        
        # Navigate to pipeline steps
        pipeline = composition.get('spec', {}).get('pipeline', [])
        
        for step in pipeline:
            input_spec = step.get('input', {})
            inline = input_spec.get('inline', {})
            template_content = inline.get('template', '')
            
            if not template_content:
                continue
            
            # Find ALL parameters referenced in this entire template
            all_params = extract_parameter_references_from_template(template_content)
            
            # Find ALL functions used in this template
            all_functions = set()
            
            # Split template into expressions
            expressions = re.findall(r'\{\{(.+?)\}\}', template_content, re.DOTALL)
            
            for expr in expressions:
                # Split by pipes for chained calls
                parts = expr.split('|')
                
                for part in parts:
                    # Remove assignment syntax
                    part = re.sub(r'\$\w+\s*:=\s*', '', part)
                    
                    # Split into tokens
                    tokens = part.strip().split()
                    
                    for token in tokens:
                        # Clean token
                        token = token.strip('()')
                        if token in GO_TEMPLATE_FUNCTIONS:
                            all_functions.add(token)
            
            # Associate each parameter with ALL functions in the template
            # Logic: when a parameter is used, the entire template executes,
            # so all functions in that template are implicitly tested
            logger.info(f"Template in step '{step.get('step', 'unknown')}':")
            logger.info(f"  Parameters: {all_params}")
            logger.info(f"  Functions: {all_functions}")
            
            for param in all_params:
                if param not in param_to_functions:
                    param_to_functions[param] = set()
                param_to_functions[param].update(all_functions)
        
        logger.info(f"Parameter-function mapping for {composition_file.name}:")
        for param, funcs in param_to_functions.items():
            logger.info(f"  {param} → {funcs}")
        
    except Exception as e:
        logger.error(f"Error analyzing parameter-function usage in {composition_file}: {e}")
    
    return param_to_functions


def calculate_function_coverage_from_parameters(
    composition_file: Path,
    covered_parameters: Set[str],
    all_functions_in_composition: Set[str]
) -> Set[str]:
    """
    Calculate which functions are covered based on which parameters are tested.
    
    Logic: If a parameter is tested (covered), then all template functions
    used with that parameter are considered covered.
    
    Args:
        composition_file: Path to composition.yaml
        covered_parameters: Set of parameters that are tested
        all_functions_in_composition: Set of all functions in the composition
        
    Returns:
        Set of function names that are covered through parameter testing
    """
    param_func_map = analyze_parameter_function_usage(composition_file)
    
    covered_functions = set()
    
    # For each covered parameter, add its associated functions
    for param in covered_parameters:
        if param in param_func_map:
            funcs = param_func_map[param]
            covered_functions.update(funcs)
            logger.info(f"Parameter '{param}' tested → covers functions: {funcs}")
    
    # Also check for functions that don't use parameters
    # (e.g., static template expressions) - these are always "covered" if they exist
    # Actually, let's be conservative and only count functions tied to tested parameters
    
    return covered_functions
