Feature: XRD defaulting on render
  Validates that render always applies XRD schema defaults: the definition (auto-resolved
  by convention from the composition directory, or overridden by an 'input definition'
  step) is passed to render via --xrd, so the XRD's schema defaults are applied to the XR
  before composing — the same definition file the validation steps use.

  Background:
    Given input claim xr.yaml
    And input composition composition.yaml
    And input functions functions.yaml

  @xrd
  Scenario: render applies schema defaults from the auto-resolved definition
    When crossplane renders the composition
    Then check that 1 resource is provisioning
    And check that resource cm has parameters with key prefix spec.forProvider.manifest.data
      | param name | param value |
      | someParam  | from-xrd    |

  @xrd
  Scenario: explicitly providing the definition applies the same schema defaults
    Given input definition definition.yaml
    When crossplane renders the composition
    Then check that 1 resource is provisioning
    And check that resource cm has parameters with key prefix spec.forProvider.manifest.data
      | param name | param value |
      | someParam  | from-xrd    |

  @xrd
  Scenario: selecting the composition directory explicitly resolves its composition and definition
    Given input composition directory xrd-defaulting
    When crossplane renders the composition
    Then check that 1 resource is provisioning
    And check that resource cm has parameters with key prefix spec.forProvider.manifest.data
      | param name | param value |
      | someParam  | from-xrd    |
