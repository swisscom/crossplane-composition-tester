@normal
Feature: S3 Bucket Versioning
  Test S3 bucket versioning configuration

  Background:
    Given input claim claim.yaml
    And input composition composition.yaml
    And input functions functions.yaml

  Scenario: Enable versioning on S3 bucket
    Given input claim is changed with parameters
      | param name       | param value |
      | spec.versioning  | true        |
    When crossplane renders the composition
    Then check that 1 resources are provisioning
