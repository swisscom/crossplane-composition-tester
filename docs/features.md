# Features
**Features** are defined in a `.feature` file. This is where you define the features you want to test. A feature file can contain one or more **scenarios**.
Each scenario is a test case made up of **steps**.

```gherkin
Feature: Test composition

  Scenario: Test 1
    Given input composition X
    And input claim X
    When crossplane renders the composition
    Then check that 3 resources are provisioning

  Scenario: Test 2
    Given input composition Y
    And input claim Y
    When crossplane renders the composition
    Then check that no resources are provisioning
```

The feature file is then passed to the `behave` command which will run each scenario as a test case. Scenarios follow
this format:

- **Given** - This is where you define and prepare the input for your test case. That can be the composition, the claim, the functions or
the *observed state*. 
- **When** - This is where you define the action you want to perform. Typically, this is where you apply the claim.
- **Then** - This is where you define the expected output of the test. 

Below we give more details about each section and which steps are currently supported.

### Given (Arrange)
Here you prepare the inputs for your test case. Since we're testing compositions, you will need to provide as input:
- the composition
- the claim you want to test the composition with
- the functions that the composition uses

**Note**: If you are using the same input (say the composition file) for multiple scenarios, you can define it in the `Background` section.
```gherkin
Feature: Test composition

  Background:
    Given input composition X

  Scenario: Test 1
    And input claim X
    And input functions X
    When Crossplane renders the composition
    Then check that 3 resources are provisioning

  Scenario: Test 2
    And input claim Y
    And input functions Y
    When crossplane renders the composition
    Then check that no resources are provisioning
```

#### Input
Every scenario needs a composition, a claim and functions as inputs. By default, we expect the structure of the folder that holds the test
to be as follows:
```
.
├── composition-tests
│   ├── functions.yaml
│   └── service-account-with-functions
│       ├── resources
│       │   └── claim.yaml
│       └── service-account.feature
└── pkg
    └── service-account
        └── composition.yaml
        └── definition.yaml
```
- The `pkg` directory holds the definition for your composite resource definitions (xrds) and their compositions. **This is what you want to test**. For example, `pkg/service-account` holds the definition of a Kubernetes service account xr and its corresponding composition.
- The `composition-tests` holds the features files. **This is where you write the tests**. Its structure should reflect that of `pkg`. 

Then each test will fetch the:
- The *composition* found in `pkg` 
- The *functions* potentially used in the compositions. They are defined in `functions.yaml` in `composition-tests`.
- The *claim* that you want to test your composition with. They are defined alongside the feature files in `composition-tests` inside the `/resources` subfolder.

With the above structure, you can reference the input files in the feature file like so:
```gherkin
Feature: Test composition

  Background:
    Given input claim claim.yaml
    # following step is optional: default input composition is composition.yaml 
    And input composition composition.yaml
    # following step is optional: default input functions is functions.yaml
    And input functions functions.yaml
```

#### The observed state

The other inputs that you can provide for your test cases are the current resources which constitute the ***observed state***.
The *observed state* describes the current state of the composite resource (xr) and composed resources, for example whether they 
are ready or how their spec looks like.
Compositions are non-deterministic in general and will give different outputs depending on the current observed state.

```gherkin
Feature: Test composition

  Background:
    Given input composition composition.yaml
    And input claim claim.yaml
    And input functions 

  Scenario: Test 1
    When Crossplane renders the composition
    Then check that 2 resources are provisioning
    
    Given change all observed resources with status READY
    And change observed resource role with parameters
      | param name            | param value |
      | status.atProvider.arn | arn::role   |
    And change observed resource default-policy with parameters
      | param name            | param value |
      | status.atProvider.arn | arn::default-policy   |
    When crossplane renders the composition
    Then check that 4 resources are provisioning and they are
      | resource-name                    |
      | role                             |
      | default-policy                   |
      | green-demo-sa-rpa-default-policy |
      | green-demo-sa                    |
```

The above scenario for testing the service-account composition showcases how you can manipulate the observed state to explore the behavior of your composition under different configurations:
1. First time you apply the claim, **there is no observed state** (i.e. no resources provisioned yet by the composition). This will provision 2 resources: the role and the default-policy.
2. **By default, all rendered resources are not ready and don't have a status** (since we're not running in a real cluster). You then mark these 2 resources as ready and provide them with the arn from the provider.
3. You then apply the claim again. This time the observed state is the 2 resources that you marked as ready. The composition will then provision 2 more resources: the role-policy-attachment and the service-account object.


This is where the bulk of your work goes when testing compositions. You need to manipulate the observed state 
to explore the behavior of your composition under different configurations (not unlike unit testing software).


### When (Act)
Here you define the actions that you take in your test case. Typically, this is where you apply the claim (equivalent 
to crossplane CLI rendering the composition).
```gherkin
Feature: Test composition

  Background:
    Given input composition composition.yaml
    And input claim claim.yaml
    And input functions functions.yaml

  Scenario: Test 1
    When crossplane renders the composition
    Then check that 3 resources are provisioning
```

### Then (Assert)
Here you define the expected output of your test case. Examples for things that you check are, the number of resources that are provisioning, the status of a resource, etc.
```gherkin
Feature: Test composition

  Background:
    Given input composition composition.yaml
    And input claim claim.yaml
    And input functions functions.yaml

  Scenario: Test 1
    When crossplane renders the composition
    Then check that 2 resources are provisioning and they are
      | resource-name                    |
      | role                             |
      | default-policy                   |
    
    And check that resource role has parameters
      | param name                 | param value   |
      | metadata.name              | rolename      |
```