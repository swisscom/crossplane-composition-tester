# Coverage Feature Guide

## Overview

The coverage feature helps you understand how thoroughly your test suite exercises your Crossplane compositions. It provides two types of coverage:

1. **Parameter Coverage**: Measures which parameters from your XRD definitions are actually used in tests
2. **Template Function Coverage**: Tracks which Go template functions are used in your compositions

## Quick Start

Enable coverage reporting by running tests with the coverage flag:

```bash
behave test -D coverage=true
```

Or set the environment variable:

```bash
export COMPOSITION_TESTER_COVERAGE=true
behave test
```

## Understanding Coverage Reports

### Parameter Coverage

Parameter coverage shows how well your tests exercise the input parameters defined in your Composite Resource Definitions (XRDs).

**What it measures:**
- Total parameters defined in XRD schema
- Parameters actually set in test claims and feature files
- Coverage percentage

**Example:**

Given this XRD definition:
```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
spec:
  versions:
    - name: v1alpha1
      schema:
        openAPIV3Schema:
          properties:
            spec:
              properties:
                serviceAccountName:      # Parameter 1
                  type: string
                serviceAccountNamespace: # Parameter 2
                  type: string
                policiesARN:            # Parameter 3
                  type: array
                  items:
                    type: string
```

And these test claims:
```yaml
# claim.yaml
spec:
  serviceAccountName: test-sa
  serviceAccountNamespace: default
  # policiesARN not set
```

The coverage report would show:
- Total Parameters: 3
- Covered Parameters: 2 (serviceAccountName, serviceAccountNamespace)
- Coverage: 66.7%
- Uncovered: policiesARN

### Template Function Coverage

Template function coverage tracks which Go template functions (built-in and Sprig) are used in your composition templates.

**What it measures:**
- Total available template functions (~170 functions)
- Functions actually used in composition templates
- Coverage percentage
- Usage count per function (when available)

**Example:**

Given this composition template:
```yaml
inline:
  template: |-
    {{ $accountId := index .context "key" }}
    {{ $name := upper "test" }}
    {{ printf "%s-%s" $accountId $name }}
```

The coverage report would show:
- Functions Used: 3 (index, upper, printf)
- Total Functions: 170
- Coverage: 1.8%
- Unused Functions: 167 other functions

## Coverage Report Formats

### Console Output

A human-readable summary printed after test execution:

```
================================================================================
CROSSPLANE COMPOSITION COVERAGE REPORT
================================================================================

📋 PARAMETER COVERAGE BY COMPOSITION
--------------------------------------------------------------------------------

  Composition: service-account-with-functions
    Total Parameters:   3
    Covered Parameters: 2
    Coverage:           66.7%
    ✓ Covered: serviceAccountName, serviceAccountNamespace
    ✗ Uncovered: policiesARN

--------------------------------------------------------------------------------
🔧 GO TEMPLATE FUNCTION COVERAGE
--------------------------------------------------------------------------------
  Total Functions:   170
  Used Functions:    5
  Coverage:          2.9%

  Top used functions:
    index
    upper
    printf
    ...

  Unused functions (165): add, sub, mul, div ... and 161 more

================================================================================
```

### JSON Report

Machine-readable format saved to `coverage-report.json`:

```json
{
  "parameter_coverage_by_composition": {
    "service-account-with-functions": {
      "composition_name": "service-account-with-functions",
      "parameters_total": 3,
      "parameters_covered": 2,
      "coverage_percentage": 66.67,
      "covered_parameters": ["serviceAccountName", "serviceAccountNamespace"],
      "uncovered_parameters": ["policiesARN"]
    }
  },
  "template_function_coverage": {
    "functions_total": 170,
    "functions_used": 5,
    "coverage_percentage": 2.94,
    "used_functions": {
      "index": 0,
      "upper": 0,
      "printf": 0
    },
    "unused_functions": ["add", "sub", "mul", ...]
  }
}
```

### YAML Report

Human-readable format saved to `coverage-report.yaml`:

```yaml
parameter_coverage_by_composition:
  service-account-with-functions:
    composition_name: service-account-with-functions
    parameters_total: 3
    parameters_covered: 2
    coverage_percentage: 66.67
    covered_parameters:
    - serviceAccountName
    - serviceAccountNamespace
    uncovered_parameters:
    - policiesARN
template_function_coverage:
  functions_total: 170
  functions_used: 5
  coverage_percentage: 2.94
  used_functions:
    index: 0
    upper: 0
    printf: 0
  unused_functions:
  - add
  - sub
  - mul
```

## Improving Coverage

### Adding Parameter Coverage

To increase parameter coverage, ensure your test claims or feature files exercise all parameters:

**Before (66.7% coverage):**
```yaml
# claim.yaml
spec:
  serviceAccountName: test-sa
  serviceAccountNamespace: default
```

**After (100% coverage):**
```yaml
# claim.yaml
spec:
  serviceAccountName: test-sa
  serviceAccountNamespace: default
  policiesARN:
    - arn:aws:iam::123456789:policy/test-policy
```

Or use feature file parameter tables:
```gherkin
Scenario: Test with all parameters
  Given input claim is changed with parameters
    | param name       | param value    |
    | spec.policiesARN | \list policy-1 |
```

### Understanding Template Function Coverage

Template function coverage is typically lower (2-10%) because:
- There are ~170 available functions
- Most compositions only use 5-20 functions
- Many functions are specialized (crypto, networking, etc.)

**What to focus on:**
- Ensure critical functions used in your templates are being tested
- Don't aim for 100% function coverage (not realistic or useful)
- Use coverage to identify which functions your compositions depend on

## CI/CD Integration

### Quality Gates

Enforce minimum coverage thresholds in your CI pipeline:

```bash
#!/bin/bash
# run_tests_with_coverage.sh

behave test -D coverage=true

# Check parameter coverage (fail if < 80%)
python3 << 'EOF'
import json
import sys

with open('coverage-report.json') as f:
    report = json.load(f)

for comp_name, coverage in report['parameter_coverage_by_composition'].items():
    pct = coverage['coverage_percentage']
    print(f"{comp_name}: {pct}% parameter coverage")
    if pct < 80:
        print(f"ERROR: Coverage below 80% threshold!")
        sys.exit(1)

print("✓ All compositions meet coverage threshold")
EOF
```

### GitLab CI Example

```yaml
test-with-coverage:
  stage: test
  script:
    - behave test -D coverage=true
    - python scripts/check_coverage.py coverage-report.json
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage-report.json
    paths:
      - coverage-report.json
      - coverage-report.yaml
```

### Jenkins Pipeline Example

```groovy
stage('Test with Coverage') {
    steps {
        sh 'behave test -D coverage=true'
        archiveArtifacts artifacts: 'coverage-report.json,coverage-report.yaml'
        
        script {
            def report = readJSON file: 'coverage-report.json'
            def coverage = report.parameter_coverage_by_composition.values()[0].coverage_percentage
            echo "Parameter Coverage: ${coverage}%"
            
            if (coverage < 80) {
                error("Coverage below threshold: ${coverage}%")
            }
        }
    }
}
```

## Best Practices

1. **Run coverage regularly**: Include in your CI/CD pipeline to track trends
2. **Set realistic thresholds**: Aim for 80-90% parameter coverage, 5-10% function coverage
3. **Focus on critical parameters**: Ensure important configuration options are tested
4. **Use coverage to find gaps**: Look at uncovered parameters to identify missing test scenarios
5. **Don't obsess over 100%**: Some parameters may be optional or rarely used
6. **Track trends**: Monitor coverage over time to ensure it doesn't decrease

## Troubleshooting

### Coverage shows 0% for all compositions

**Cause**: No definition.yaml files found or test directory structure issue

**Solution**: Ensure your directory structure follows the convention:
```
test/
├── composition-tests/
│   └── <composition-name>/
│       ├── resources/
│       │   └── claim.yaml
│       └── feature.feature
└── pkg/
    └── <composition-name>/
        ├── composition.yaml
        └── definition.yaml
```

### Parameters not detected in feature files

**Cause**: Parameter table format not recognized

**Solution**: Ensure your feature file uses correct table format:
```gherkin
Given input claim is changed with parameters
  | param name       | param value |
  | spec.paramName   | value       |
```

### Coverage reports not generated

**Cause**: Coverage mode not enabled

**Solution**: Use `-D coverage=true` flag or set `COMPOSITION_TESTER_COVERAGE=true`

## API Reference

### Coverage Models

```python
from steps.coverage.models import (
    ParameterCoverage,
    TemplateFunctionCoverage,
    CoverageReport
)

# Generate report programmatically
from steps.coverage.reporter import generate_coverage_report

report = generate_coverage_report(Path("test"))
print(report.to_json())
```

### Programmatic Usage

```python
from pathlib import Path
from steps.coverage.parameter_coverage import calculate_parameter_coverage

coverage = calculate_parameter_coverage(
    composition_name="my-composition",
    definition_file=Path("test/pkg/my-composition/definition.yaml"),
    composition_dir=Path("test/pkg/my-composition"),
    feature_dir=Path("test/composition-tests/my-composition")
)

print(f"Coverage: {coverage.coverage_percentage}%")
print(f"Uncovered: {coverage.uncovered_parameters}")
```
