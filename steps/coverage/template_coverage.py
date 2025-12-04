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

"""Template function coverage tracking for Go templating."""

import logging
import re
from pathlib import Path
from typing import Set, Dict
import yaml

from steps.coverage.models import TemplateFunctionCoverage

logger = logging.getLogger("xplane-composition-tester logger")


# Common Go template functions (built-in + sprig)
# This is a representative list of commonly available functions
GO_TEMPLATE_FUNCTIONS = {
    # Built-in Go template functions
    "and", "call", "html", "index", "slice", "js", "len", "not", "or",
    "print", "printf", "println", "urlquery",
    
    # Sprig string functions
    "trim", "trimAll", "trimSuffix", "trimPrefix", "upper", "lower", "title",
    "untitle", "repeat", "substr", "nospace", "trunc", "abbrev", "abbrevboth",
    "initials", "randAlphaNum", "randAlpha", "randAscii", "randNumeric",
    "swapcase", "shuffle", "snakecase", "camelcase", "kebabcase", "wrap",
    "wrapWith", "contains", "hasPrefix", "hasSuffix", "quote", "squote",
    "cat", "indent", "nindent", "replace", "plural", "sha1sum", "sha256sum",
    "adler32sum", "toString",
    
    # Sprig string list functions
    "join", "split", "splitList", "splitn", "sortAlpha",
    
    # Sprig integer/math functions
    "add", "add1", "sub", "div", "mod", "mul", "max", "min", "floor", "ceil",
    "round", "biggest", "until", "untilStep",
    
    # Sprig date functions
    "now", "ago", "date", "dateInZone", "duration", "durationRound", "unixEpoch",
    "dateModify", "htmlDate", "htmlDateInZone", "toDate", "mustToDate",
    
    # Sprig defaults functions
    "default", "empty", "coalesce", "fromJson", "toJson", "toPrettyJson",
    "toRawJson", "mustFromJson", "mustToJson", "mustToPrettyJson",
    "mustToRawJson",
    
    # Sprig dict functions
    "dict", "get", "set", "unset", "hasKey", "pluck", "dig", "merge",
    "mergeOverwrite", "keys", "pick", "omit", "values", "deepCopy",
    
    # Sprig list functions
    "list", "first", "rest", "last", "initial", "append", "prepend", "concat",
    "reverse", "uniq", "without", "has", "compact", "chunk",
    
    # Sprig type conversion
    "atoi", "int64", "int", "float64", "toDecimal", "toStrings",
    
    # Sprig encoding functions
    "b64enc", "b64dec", "b32enc", "b32dec",
    
    # Sprig reflection/type
    "typeOf", "typeIs", "typeIsLike", "kindOf", "kindIs", "deepEqual",
    
    # Sprig crypto
    "genPrivateKey", "derivePassword", "buildCustomCert", "genCA",
    "genSelfSignedCert", "genSignedCert", "encryptAES", "decryptAES",
    
    # Sprig network
    "getHostByName",
    
    # Sprig regex
    "regexMatch", "regexFindAll", "regexFind", "regexReplaceAll",
    "regexReplaceAllLiteral", "regexSplit", "mustRegexMatch",
    "mustRegexFindAll", "mustRegexFind", "mustRegexReplaceAll",
    "mustRegexReplaceAllLiteral", "mustRegexSplit",
    
    # Sprig UUID
    "uuidv4",
    
    # Flow control
    "fail", "ternary",
    
    # Misc
    "env", "expandenv", "base", "dir", "ext", "clean", "isAbs",
}


class TemplateFunctionTracker:
    """Tracks Go template function usage across test runs."""
    
    def __init__(self):
        """Initialize the tracker."""
        self.composition_functions: Set[str] = set()  # Functions found in composition templates
        self.used_functions: Dict[str, int] = {}
        self.enabled = False
    
    def enable(self):
        """Enable function tracking."""
        self.enabled = True
        logger.info("Template function tracking enabled")
    
    def disable(self):
        """Disable function tracking."""
        self.enabled = False
    
    def set_composition_functions(self, functions: Set[str]):
        """
        Set the functions that are actually used in composition templates.
        
        Args:
            functions: Set of function names found in compositions
        """
        self.composition_functions = functions
        logger.info(f"Tracking {len(functions)} functions from composition templates")
    
    def record_function_usage(self, function_name: str):
        """
        Record that a function was used.
        
        Args:
            function_name: Name of the function used
        """
        if not self.enabled:
            return
        
        if function_name in self.composition_functions:
            self.used_functions[function_name] = self.used_functions.get(function_name, 0) + 1
    
    def get_coverage(self) -> TemplateFunctionCoverage:
        """
        Get the current template function coverage.
        
        Returns:
            TemplateFunctionCoverage object with coverage of composition functions
        """
        unused = sorted(list(self.composition_functions - set(self.used_functions.keys())))
        
        return TemplateFunctionCoverage(
            functions_total=len(self.composition_functions),
            functions_used=len(self.used_functions),
            used_functions=dict(sorted(self.used_functions.items())),
            unused_functions=unused
        )
    
    def reset(self):
        """Reset tracking data."""
        self.used_functions.clear()
        self.composition_functions.clear()


# Global tracker instance
_global_tracker = TemplateFunctionTracker()


def get_global_tracker() -> TemplateFunctionTracker:
    """Get the global template function tracker."""
    return _global_tracker


def extract_template_functions_from_composition(composition_file: Path) -> Set[str]:
    """
    Extract template functions used in a composition file.
    
    This performs static analysis of the composition's inline templates
    to identify which functions are called.
    
    Args:
        composition_file: Path to composition.yaml
        
    Returns:
        Set of function names found in the templates
    """
    functions_found = set()
    
    try:
        with open(composition_file, 'r') as f:
            composition = yaml.safe_load(f)
        
        # Navigate to pipeline steps
        pipeline = composition.get('spec', {}).get('pipeline', [])
        
        for step in pipeline:
            input_spec = step.get('input', {})
            
            # Check for inline templates
            inline = input_spec.get('inline', {})
            template_content = inline.get('template', '')
            
            if template_content:
                # Extract function calls from template
                # Pattern: {{ functionName ... }} or {{functionName ...}}
                # Also handles chained calls like: {{ .var | functionName }}
                
                # Find all template expressions
                template_exprs = re.findall(r'\{\{(.+?)\}\}', template_content, re.DOTALL)
                
                for expr in template_exprs:
                    # Look for function calls
                    # Functions are typically: functionName args or $var:=functionName args
                    # or piped: .var | functionName args
                    
                    # Split by pipes for chained calls
                    parts = expr.split('|')
                    
                    for part in parts:
                        # Remove assignment syntax like $var:=
                        part = re.sub(r'\$\w+\s*:=\s*', '', part)
                        
                        # Split into tokens
                        tokens = part.strip().split()
                        
                        for token in tokens:
                            # Check if token looks like a function (lowercase, no special chars at start)
                            # Skip keywords, variables, and operators
                            if token and token[0].isalpha() and token in GO_TEMPLATE_FUNCTIONS:
                                functions_found.add(token)
                                logger.debug(f"Found function '{token}' in {composition_file.name}")
        
        logger.info(f"Extracted {len(functions_found)} template functions from {composition_file.name}")
        
    except Exception as e:
        logger.error(f"Error extracting template functions from {composition_file}: {e}")
    
    return functions_found


def extract_all_composition_functions(test_dir: Path) -> Set[str]:
    """
    Extract all template functions that are actually defined in composition templates.
    
    This determines what functions SHOULD be tested based on what's in the compositions,
    not what's theoretically possible in Go templates.
    
    Args:
        test_dir: Root test directory containing pkg/ subdirectories
        
    Returns:
        Set of function names found in composition templates
    """
    all_functions = set()
    
    pkg_dir = test_dir / "pkg"
    if not pkg_dir.exists():
        logger.warning(f"No pkg directory found at {pkg_dir}")
        return all_functions
    
    # Find all composition.yaml files
    for composition_file in pkg_dir.rglob("composition.yaml"):
        functions = extract_template_functions_from_composition(composition_file)
        all_functions.update(functions)
        logger.info(f"  {composition_file.parent.name}: {len(functions)} functions")
    
    logger.info(f"Total {len(all_functions)} unique template functions across all compositions")
    
    return all_functions
