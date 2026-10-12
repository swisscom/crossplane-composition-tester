Feature: Service Account composition
  Tests the service account compositions

  Background:
    Given input claim claim.yaml
    # following step is optional: default input composition is composition.yaml
    And input composition composition.yaml
    # following step is optional: default input functions is functions.yaml
    And input functions functions.yaml
    And input definition definition.yaml
    Then check that the claim is valid
    And check that no resources are provisioning

  @critical
  Scenario: service account with default policies

    # render 1
    When crossplane renders the composition
    Then check that 2 resources are provisioning
    And check that resource role has parameters
      | param name                  |
      | metadata.labels             |
      | spec.providerConfigRef.name |
    And check that resource role has parameters
      | param name    | param value   |
      | metadata.name | green-demo-sa |
    # | spec.forProvider.permissionsBoundary | {regexp}*/example-policy-cdk-pipeline-permission-boundary |
    And check that resource role has parameters with key prefix spec
      | param name           | param value |
      | statusTestWordLength | 5           |

    # render 2
    Given change observed resource role with status NOT READY and parameters
      | param name            | param value |
      | status.atProvider.arn | arn::role   |
    And change observed resource default-policy with status NOT READY and parameters
      | param name            | param value         |
      | status.atProvider.arn | arn::default-policy |
    # Set status of observed resource from values file, which is easier for values with multiline strings like policy document
    And change observed resource default-policy with parameters from values file resource-params-example.yaml
    When crossplane renders the composition
    Then check that 2 resources are provisioning and they are
      | resource-name  |
      | role           |
      | default-policy |
    And check that resource role has parameters with key prefix spec
      | param name           | param value |
      | statusTestWordLength | 3           |
    And check that xr has status parameters
      | param name | param value                |
      | hello      | world                      |
      | just       | a multiline string example |

    # render 3
    Given change observed resource role with status READY
    And change observed resource default-policy with status READY
    When crossplane renders the composition
    Then check that 4 resources are provisioning and they are
      | resource-name                    |
      | role                             |
      | default-policy                   |
      | green-demo-sa-rpa-default-policy |
      | green-demo-sa                    |
    And check that resource green-demo-sa-rpa-default-policy has parameters
      | param name                | param value   |
      | spec.forProvider.roleName | green-demo-sa |

    # render 4
    Given change observed resource green-demo-sa-rpa-default-policy with status READY
    And change observed resource green-demo-sa with status READY
    When crossplane renders the composition
    Then check that the xr is valid
  # Then composite is READY -> depends on the implementation of https://github.com/crossplane/crossplane/issues/4810 in the renderer

  @normal
  Scenario: service account with 1 policyARN
    Given input claim is changed with parameters
      | param name       | param value       |
      | spec.policiesARN | \\list policyArn1 |
    Then check that the claim is valid

    When crossplane renders the composition
    Then check that 2 resources are provisioning

    Given change observed resource role with status READY and parameters
      | param name            | param value |
      | status.atProvider.arn | arn::role   |
    And change observed resource default-policy with status READY and parameters
      | param name            | param value         |
      | status.atProvider.arn | arn::default-policy |
    When crossplane renders the composition
    Then check that 5 resources are provisioning and they are
      | resource-name                    |
      | role                             |
      | default-policy                   |
      | green-demo-sa-rpa-default-policy |
      | green-demo-sa-rpa-0              |
      | green-demo-sa                    |
    And check that resource green-demo-sa-rpa-0 has parameters
      | param name                 | param value   |
      | spec.forProvider.roleName  | green-demo-sa |
      | spec.forProvider.policyArn | policyArn1    |
    And check that the xr is valid

    Given change observed resource green-demo-sa-rpa-default-policy with status READY
    Given change observed resource green-demo-sa-rpa-0 with status READY
    And change observed resource green-demo-sa with status READY
    When crossplane renders the composition
    # Then composite is READY -> depends on the implementation of https://github.com/crossplane/crossplane/issues/4810 in the renderer
    Then check that 5 resources are provisioning


  @minor
  Scenario: service account with 2 policyARNs

    # render 1
    Given input claim is changed with parameters
      | param name       | param value                  |
      | spec.policiesARN | \\list policyArn1,policyArn2 |
    Then check that the claim is valid

    When crossplane renders the composition
    Then check that 2 resources are provisioning

    # render 2
    Given change following observed resources with status READY
      | resource-name  |
      | role           |
      | default-policy |
    And change observed resource role with parameters
      | param name            | param value |
      | status.atProvider.arn | arn::role   |
    And change observed resource default-policy with parameters
      | param name            | param value         |
      | status.atProvider.arn | arn::default-policy |
    When crossplane renders the composition
    Then check that 6 resources are provisioning and they are
      | resource-name                    |
      | role                             |
      | default-policy                   |
      | green-demo-sa-rpa-default-policy |
      | green-demo-sa-rpa-0              |
      | green-demo-sa-rpa-1              |
      | green-demo-sa                    |
    And check that resource green-demo-sa-rpa-0 has parameters
      | param name                 | param value   |
      | spec.forProvider.roleName  | green-demo-sa |
      | spec.forProvider.policyArn | policyArn1    |

    # render 3
    Given change all observed resources with status READY
    When crossplane renders the composition
    Then log desired resources

    # render 4
    Given change all observed resources with status NOT READY
    When crossplane renders the composition
    Then log desired resources

# Then fail here
# Then composite is READY -> depends on the implementation of https://github.com/crossplane/crossplane/issues/4810 in the renderer

#  @normal
#  Scenario: service account with 2 custom policies
#    Given claim claim_service_account_with_2_custom_policies.yaml
#    And we apply the claim
#    Then check that 4 resources are provisioning and they are
#      | resource-name          |
#      | role                   |
#      | default-policy         |
#      | policy-custom-policy-1 |
#      | policy-custom-policy-2 |
#
#    Given all resources are READY
#    And resource policy-custom-policy-1 is updated with
#      | param name            | param value      |
#      | status.atProvider.arn | customPolicyArn1 |
#    And resource policy-custom-policy-2 is updated with
#      | param name            | param value      |
#      | status.atProvider.arn | customPolicyArn2 |
#    And resource default-policy is updated with
#      | param name            | param value         |
#      | status.atProvider.arn | arn::default-policy |
#    When crossplane renders the composition
#    Then check that 7 resources are provisioning


#   Scenario: service account with 2 policyARNs
#     # similar

#   Scenario: service account with 1 custom policy
#   Scenario: service account with 2 custom policies
#   Scenario: service account with 2 policyARNs and 2 custom policies
