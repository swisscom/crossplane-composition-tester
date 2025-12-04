# Coverage Feature Guide

## Overview

The coverage feature helps you understand how thoroughly your test suite exercises your Crossplane compositions by measuring **parameter coverage** - which parameters from your XRD definitions are actually tested in your test suite.

This helps you:
- Identify untested configuration options
- Ensure comprehensive test coverage of composition inputs
- Track coverage trends over time
- Set quality gates in CI/CD pipelines

## Quick Start

Enable coverage reporting by running tests with the coverage flag:

```bash
# Using the test runner (recommended)
./tests_runner.sh test --coverage

# Using behave directly
behave test -D coverage=true
```

Or set the environment variable:

```bash
export COMPOSITION_TESTER_COVERAGE=true
behave test
```

## Understanding Parameter Coverage

Parameter coverage shows how well your tests exercise the input parameters defined in your Composite Resource Definitions (XRDs).

**What it measures:**
- All parameters defined in XRD OpenAPI schema (including nested properties)
- Parameters actually set in test claims and feature files
- Coverage percentage per composition

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

### How Parameters Are Detected

**From Claims:**
- Parameters set directly in `claim.yaml` files
- Default values in XRD schemas don't count as "covered"

**From Feature Files:**
- Parameters set using `Given input claim is changed with parameters` steps
- Parameter tables in Gherkin scenarios

**Nested Properties:**
- Object properties are tracked individually (e.g., `lifecycleRules.enabled`)
- Array items with object schemas have their properties tracked

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
    Covered Parameters: 3
    Coverage:           100.0%
    ✓ Covered: policiesARN, serviceAccountName, serviceAccountNamespace

  Composition: s3-bucket
    Total Parameters:   8
    Covered Parameters: 3
    Coverage:           37.5%
    ✓ Covered: bucketName, encryption, versioning
    ✗ Uncovered: lifecycleRules, lifecycleRules.enabled, lifecycleRules.expirationDays, lifecycleRules.id, tags

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
      "parameters_covered": 3,
      "coverage_percentage": 100.0,
      "covered_parameters": ["policiesARN", "serviceAccountName", "serviceAccountNamespace"],
      "uncovered_parameters": []
    },
    "s3-bucket": {
      "composition_name": "s3-bucket",
      "parameters_total": 8,
      "parameters_covered": 3,
      "coverage_percentage": 37.5,
      "covered_parameters": ["bucketName", "encryption", "versioning"],
      "uncovered_parameters": ["lifecycleRules", "lifecycleRules.enabled", "lifecycleRules.expirationDays", "lifecycleRules.id", "tags"]
    }
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
    parameters_covered: 3
    coverage_percentage: 100.0
    covered_parameters:
    - policiesARN
    - serviceAccountName
    - serviceAccountNamespace
    uncovered_parameters: []
  s3-bucket:
    composition_name: s3-bucket
    parameters_total: 8
    parameters_covered: 3
    coverage_percentage: 37.5
    covered_parameters:
    - bucketName
    - encryption
    - versioning
    uncovered_parameters:
    - lifecycleRules
    - lifecycleRules.enabled
    - lifecycleRules.expirationDays
    - lifecycleRules.id
    - tags
```

### Allure Integration

When coverage is enabled, data is automatically integrated into Allure reports:

**1. Environment Properties** (`allure_reports/environment.properties`)
```properties
Coverage.service_account_with_functions=100.0%
Coverage.service_account_with_functions.covered=3/3
Coverage.s3_bucket=37.5%
Coverage.s3_bucket.covered=3/8
```

This appears in Allure's Environment widget on the overview page.

**2. Test Attachments**
- `Coverage Report (JSON)` - Full JSON report
- `Coverage Report (YAML)` - Human-readable YAML
- `Coverage Summary` - Formatted text summary

**3. Metadata Files**
- `executor.json` - Build metadata with "Coverage Report" designation
- `categories.json` - Test categorization

**To view in Allure:**
```bash
allure generate allure_reports/ -o allure-report --clean
allure open allure-report
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

### Coverage Best Practices

1. **Start with critical parameters**: Focus on testing parameters that affect core functionality first
2. **Test edge cases**: Include scenarios with optional parameters set and unset
3. **Cover nested objects**: Ensure complex object parameters are fully tested
4. **Use feature scenarios**: Leverage multiple scenarios to cover different parameter combinations
5. **Track trends**: Monitor coverage over time to prevent regression

## CI/CD Integration

### Quality Gates

Enforce minimum coverage thresholds in your CI pipeline:

```bash
#!/bin/bash
# run_tests_with_coverage.sh

./tests_runner.sh test --coverage

# Check parameter coverage (fail if < 80%)
python3 << 'EOF'
import json
import sys

with open('coverage-report.json') as f:
    report = json.load(f)

failed = False
for comp_name, coverage in report['parameter_coverage_by_composition'].items():
    pct = coverage['coverage_percentage']
    print(f"{comp_name}: {pct}% parameter coverage")
    if pct < 80:
        print(f"ERROR: {comp_name} coverage {pct}% below 80% threshold!")
        failed = True

if failed:
    sys.exit(1)
    
print("✓ All compositions meet coverage threshold")
EOF
```

### GitLab CI Example

```yaml
test-with-coverage:
  stage: test
  script:
    - ./tests_runner.sh test --coverage
    - python3 scripts/check_coverage.py coverage-report.json
  artifacts:
    reports:
      junit: allure_reports/*.json
    paths:
      - coverage-report.json
      - coverage-report.yaml
      - allure_reports/
```

### Jenkins Pipeline Example

```groovy
stage('Test with Coverage') {
    steps {
        sh './tests_runner.sh test --coverage'
        
        // Archive coverage reports
        archiveArtifacts artifacts: 'coverage-report.json,coverage-report.yaml'
        
        // Publish Allure report with coverage
        allure([
            includeProperties: false,
            jdk: '',
            properties: [],
            reportBuildPolicy: 'ALWAYS',
            results: [[path: 'allure_reports']]
        ])
        
        // Check coverage threshold
        script {
            def report = readJSON file: 'coverage-report.json'
            report.parameter_coverage_by_composition.each { comp, coverage ->
                def pct = coverage.coverage_percentage
                echo "${comp}: ${pct}% coverage"
                
                if (pct < 80) {
                    error("Coverage below threshold: ${pct}%")
                }
            }
        }
    }
}
```

### GitHub Actions Example

```yaml
name: Test with Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          curl -sL "https://raw.githubusercontent.com/crossplane/crossplane/master/install.sh" | sh
      
      - name: Run tests with coverage
        run: ./tests_runner.sh test --coverage
      
      - name: Upload coverage reports
        uses: actions/upload-artifact@v3
        with:
          name: coverage-reports
          path: |
            coverage-report.json
            coverage-report.yaml
      
      - name: Check coverage threshold
        run: |
          python3 -c "
          import json, sys
          report = json.load(open('coverage-report.json'))
          failed = any(c['coverage_percentage'] < 80 
                      for c in report['parameter_coverage_by_composition'].values())
          sys.exit(1 if failed else 0)
          "
```

## Best Practices

1. **Run coverage regularly**: Include `--coverage` flag in your CI/CD pipeline to track trends
2. **Set realistic thresholds**: Aim for 80-90% parameter coverage for production compositions
3. **Focus on critical parameters**: Ensure important configuration options are tested first
4. **Use coverage to find gaps**: Review uncovered parameters to identify missing test scenarios
5. **Don't obsess over 100%**: Some parameters may be optional, deprecated, or edge-case only
6. **Track trends over time**: Monitor coverage percentage to ensure it doesn't decrease with new changes
7. **Document intentional gaps**: If certain parameters are intentionally untested, document why
8. **Test parameter combinations**: Don't just set parameters individually - test realistic combinations

## Troubleshooting

### Coverage shows 0% for all compositions

**Cause**: No `definition.yaml` files found or test directory structure issue

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
        └── definition.yaml    # Must exist!
```

### Parameters not detected in claims

**Cause**: Parameter path doesn't match XRD schema

**Solution**: Verify parameter paths match exactly:
- Check XRD schema structure under `spec.properties`
- Use correct nesting (e.g., `spec.serviceAccountName` not just `serviceAccountName`)
- Ensure YAML syntax is valid in claim files

### Parameters not detected in feature files

**Cause**: Parameter table format not recognized

**Solution**: Ensure your feature file uses correct table format with `spec.` prefix:
```gherkin
Given input claim is changed with parameters
  | param name       | param value |
  | spec.paramName   | value       |
```

### Coverage reports not generated

**Cause**: Coverage mode not enabled

**Solution**: 
- Use `./tests_runner.sh test --coverage` (recommended)
- Or `behave test -D coverage=true`
- Or set `export COMPOSITION_TESTER_COVERAGE=true`

### Allure environment properties not showing coverage

**Cause**: Allure report not regenerated after coverage run

**Solution**: 
```bash
# Clean and regenerate Allure report
allure generate allure_reports/ -o allure-report --clean
allure open allure-report
```

### Nested parameters show as uncovered

**Cause**: Parent object set but nested properties not explicitly set

**Solution**: Set nested properties explicitly:
```yaml
# Instead of this
spec:
  config: {}

# Do this
spec:
  config:
    enabled: true
    timeout: 30
```

## API Reference

### Coverage Models

```python
from steps.coverage.models import (
    ParameterCoverage,
    CoverageReport
)

# ParameterCoverage contains:
# - composition_name: str
# - parameters_total: int
# - parameters_covered: int
# - covered_parameters: List[str]
# - uncovered_parameters: List[str]
# - coverage_percentage: float (property)

# CoverageReport contains:
# - parameter_coverage_by_composition: Dict[str, ParameterCoverage]
```

### Programmatic Usage

```python
from pathlib import Path
from steps.coverage.reporter import generate_coverage_report, print_coverage_summary

# Generate full coverage report
report = generate_coverage_report(Path("test"))

# Print to console
print_coverage_summary(report)

# Export to JSON/YAML
json_str = report.to_json(indent=2)
yaml_str = report.to_yaml()

# Access data
for comp_name, coverage in report.parameter_coverage_by_composition.items():
    print(f"{comp_name}: {coverage.coverage_percentage}%")
    print(f"Uncovered: {coverage.uncovered_parameters}")
```

### Calculate Coverage for Specific Composition

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
print(f"Covered: {coverage.covered_parameters}")
print(f"Uncovered: {coverage.uncovered_parameters}")
```

### Extract Parameters from XRD

```python
from pathlib import Path
from steps.coverage.parameter_coverage import extract_parameters_from_definition

# Get all parameters defined in XRD
parameters = extract_parameters_from_definition(
    Path("test/pkg/my-composition/definition.yaml")
)

print(f"Found {len(parameters)} parameters:")
for param in sorted(parameters):
    print(f"  - {param}")
```

## Multi-Composition Coverage

When you have multiple compositions in your project, coverage is calculated separately for each:

```
test/
├── composition-tests/
│   ├── service-account/
│   └── s3-bucket/
└── pkg/
    ├── service-account/
    └── s3-bucket/
```

Example output:
```
Composition: service-account
  Coverage: 100.0% (3/3 parameters)
  
Composition: s3-bucket
  Coverage: 37.5% (3/8 parameters)
```

This allows you to track coverage per product/composition independently.
