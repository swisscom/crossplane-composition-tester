@critical
Feature: S3 Bucket Basic Provisioning
  Test basic S3 bucket creation with encryption

  Background:
    Given input claim claim.yaml
    And input composition composition.yaml
    And input functions functions.yaml

  Scenario: Create encrypted S3 bucket
    When crossplane renders the composition
    Then check that 1 resources are provisioning
    And check that resource my-test-bucket-123 has parameters
      | param name                     | param value      |
      | spec.forProvider.acl           | private          |
