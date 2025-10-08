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

# from __future__ import absolute_import, print_function
import logging
import subprocess

from behave import *

from steps.utils.checkers import *
from steps.utils.constants import *
from steps.utils.setters import *
from steps.utils.utils import *

logger = logging.getLogger("xplane-composition-tester logger")
logger.setLevel(logging.INFO)


# use_step_matcher("parse")
# use_step_matcher("cfparse")


# doc: https://behave.readthedocs.io/en/latest/

@given("change observed xr with parameters")
@given("input claim is changed with parameters")
def xr_is_updated_with(ctx: Context) -> None:
    """
    Update the XR (claim) with parameters from the table.

    Arguments:
        ctx (Context): behave context

    Raises:
        AssertionError: if no claim/XR found in context
    """
    updates = {row["param name"]: parse_value_cmd(row["param value"]) for row in ctx.table}
    update_xr_params(ctx, updates)


@given("input claim {claim_file}")
def prepare_claim(ctx: Context, claim_file: str) -> None:
    # logger.info(f"get the claim {claim_file}")
    
    # TODO: consider loading the claim as desired composite, and any subsequent observed file fed will merge into the desired xr and not just replace it
    base_path = getattr(ctx, "base_path", None)
    # Prepare file as claim to be used as claim validation
    prepare_file(
        ctx,
        CLAIM,
        f"{base_path}/resources/{claim_file}",
        load_into_context=False,
        attach_to_allure=True,
    )
    
    # Prepare file as observed xr and load it into the context to be used for subsequent renders
    prepare_file(
        ctx,
        CTX_DESIRED_COMPOSITE,
        f"{base_path}/resources/{claim_file}",
        load_into_context=True,
        attach_to_allure=False,
    )
    
    # Loading a claim in the middle of the scenario should reset any previous updates to the xr
    if hasattr(ctx, XR_UPDATES):
        delattr(ctx, XR_UPDATES)

    
@given("input composition directory {composition_directory} and definition file {definition_file}")
def prepare_definition_from_directory(ctx: Context, composition_directory: str, definition_file: str) -> None:
    """Retrieve the definition file for the test from the specified directory under 'pkg' and check if it exists.

    Arguments:
        ctx {Context} -- behave context
        composition_directory {str} -- composition directory
        definition_file {str} -- composition filename
    """
    prepare_file(
        ctx,
        DEFINITION,
        f"{ctx.project_root}/pkg/{composition_directory}/{definition_file}",
    )


@given("input composition directory {composition_directory} and file {composition_file}")
def prepare_composition_from_directory(ctx: Context, composition_directory: str, composition_file: str) -> None:
    """Retrieve the composition file for the test from the specified directory under 'pkg' and check if it exists.

    Arguments:
        ctx {Context} -- behave context
        composition_directory {str} -- composition directory
        composition_file {str} -- composition filename
    """
    prepare_file(
        ctx,
        COMPOSITION,
        f"{ctx.project_root}/pkg/{composition_directory}/{composition_file}",
        load_into_context=False,
        attach_to_allure=False,
    )
    
    
@given("input compositions directory {compositions_directory}")
def prepare_compositions_directory(ctx: Context, compositions_directory: str) -> None:
    """Prepare working directory with the compositions for the test. This handles the case where compositions
    are located in a different directory than the default /pkg directory.

    Arguments:
        ctx {Context} -- behave context
    """
    ctx.compositions_directory = compositions_directory
    logger.info(
        f"Current working directory with compositions {compositions_directory}")


@given("input definition {definition_file_name}")
def prepare_definition(ctx: Context, definition_file_name: str) -> None:
    prepare_file(
        ctx,
        DEFINITION,
        f"{ctx.compositions_directory}/{definition_file_name}",
    )


@given("input composition {composition_file}")
def prepare_composition(ctx: Context, composition_file: str) -> None:
    """Retrieve the composition file for the test and check if it exists. By default, the compositions are
    retrieved from a dedicated pkg directory at the root of the project, that mirrors the structure of the test directory
    will all the features.

    Arguments:
        ctx {Context} -- behave context
        composition_file {str} -- composition filename
    """
    # logger.info(f"get test composition {composition_file}")
    prepare_file(
        ctx,
        COMPOSITION,
        f"{ctx.compositions_directory}/{composition_file}",
        load_into_context=False,
        attach_to_allure=False,
    )


@given("input environment config {envconfig_file}")
@given("input environment config {envconfig_file} file")
def prepare_environment_config(ctx: Context, envconfig_file: str) -> None:
    """Retrieve the environment config file for the test and check if it exists. By default, the envconfig file should be at the
    same level as the parent directory containing all features to test.

    Arguments:
        ctx {Context} -- behave context
        envconfig_file {str} -- environment configuration filename
    """

    features_directory = ctx.base_path.parent
    prepare_file(
        ctx,
        ENVCONFIG,
        f"{features_directory}/{envconfig_file}",
        load_into_context=False,
        attach_to_allure=False,
    )


@given("input functions {functions_file}")
def prepare_functions(ctx: Context, functions_file: str) -> None:
    """Retrieve the functions file for the test and check if it exists. By default, the functions file
    should be at the same level as the parent directory containing all features to test.

    Arguments:
        ctx {Context} -- behave context
        functions_file {str} -- functions filepath
    """

    functions_folder_path = ctx.functions_folder_path
    if ctx.on_ci:
        # If running on CI, use the CI version of the functions file
        functions_file_name = functions_file.split(".yaml")[0]
        functions_file = f"{functions_file_name}-ci.yaml"
    prepare_file(
        ctx,
        FUNCTIONS,
        f"{functions_folder_path}/{functions_file}",
        load_into_context=False,
        attach_to_allure=False,
    )


@given("input observed state {observed_state_file} for next rendering")
def prepare_observed_state(ctx: Context, observed_state_file: str) -> None:
    """Takes a custom observed state filename and stores it in the context.

    Arguments:
        ctx {Context} -- behave context
        observed_state_file {str} -- observed state filepath
    """
    base_path = getattr(ctx, "base_path", None)
    filepath = f"{base_path}/resources/{observed_state_file}"
    prepare_file(
        ctx,
        OBSERVED,
        filepath,
        load_into_context=False,
        attach_to_allure=True
    )

    # Set the current observed to the observed state from the file
    with open(filepath, mode="r", encoding="utf-8") as file:
        content = file.read()
        load_xr_and_resources_into_context(ctx, content, desired=False)

    # Loading an observed state from file overrides any existing changes to composed resources from the scenario
    if hasattr(ctx, RESOURCES_UPDATES):
        delattr(ctx, RESOURCES_UPDATES)
    # if hasattr(ctx, XR_UPDATES):
    #     delattr(ctx, XR_UPDATES)


@step("crossplane renders the composition")
def render(ctx: Context) -> None:
    # get what is needed from the context:
    #  - claim/xr
    #  - composition
    #  - observed resources
    #  - functions - default ones would be in xplane-pkg repo
    #  - context from the environment file - default ones would be in xplane-pkg repo

    # TODO: Add timeout to render?

    # logger.info("rendering composition")

    args = prepare_render_args(ctx, log_input=ctx.debug_mode)
    
    try:
        out = subprocess.check_output(args, universal_newlines=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as proc_exc:
        logger.error(f"Error rendering: {proc_exc.output}")
        assert False, f"error rendering: {proc_exc.output}"

    # Attach output of render to allure report
    allure.attach(
        out,
        name="render output",
    )

    if ctx.debug_mode:
        save_rendered_output(ctx, out)

    load_xr_and_resources_into_context(ctx, out)
    
    
@then("check that the claim is valid")
def validate_claim(ctx: Context) -> None:
    # get what is needed from the context:
    #  - The claim
    #  - definition
    crossplane_validate_schema(ctx.definition_filepath, ctx.claim_filepath)
    

@then("check that the claim is invalid")
def validate_wrong_claim(ctx: Context) -> None:
    crossplane_validate_schema(ctx.definition_filepath, ctx.claim_filepath, must_be_valid=False)


@then("check that the xr is valid")
def validate_xr(ctx: Context) -> None:
    # get what is needed from the context:
    #  - file with raw string output of xr from render
    #  - definition
    dump_yaml_to_file(TMP_XR_FILE_PATH, get_from_context(ctx, CTX_DESIRED_COMPOSITE, assert_exists=True))
    crossplane_validate_schema(ctx.definition_filepath, TMP_XR_FILE_PATH)
    

@then("check that the xr is invalid")
def validate_wrong_xr(ctx: Context) -> None:
    # crossplane_validate_schema(ctx.definition_filepath, TMP_XR_VALIDATION_FILE_PATH, must_be_valid=False)
    dump_yaml_to_file(TMP_XR_FILE_PATH, get_from_context(ctx, CTX_DESIRED_COMPOSITE, assert_exists=True))
    crossplane_validate_schema(ctx.definition_filepath, TMP_XR_FILE_PATH, must_be_valid=False)


@then("check that no resources are provisioning")
def check_no_resources(ctx: Context) -> None:
    # ignore the xr, get only desired resources
    desired_resources = get_from_context(
        ctx, CTX_DESIRED_RESOURCES, assert_exists=False)
    check_resources_are_empty(desired_resources)


@step("check that {resource_count:d} resource is provisioning")
@step("check that {resource_count:d} resources are provisioning")
def check_resource_count(ctx: Context, resource_count: int) -> None:
    # logger.info(f"check that number of resources is {resource_count}")

    # ignore the xr, get only desired resources
    desired_resources = get_from_context(ctx, CTX_DESIRED_RESOURCES, assert_exists=True)
    check_resources(desired_resources, resource_count)


@step("check that {resource_count:d} resource is provisioning and it is")
@step("check that {resource_count:d} resources are provisioning and they are")
def check_resource_count_and_names(ctx: Context, resource_count: int) -> None:
    # logger.info(f"check that number of resources is {resource_count}")

    expected_resources_names = [row["resource-name"] for row in ctx.table]

    # ignore the xr, get only desired resources
    desired_resources = get_from_context(ctx, CTX_DESIRED_RESOURCES, assert_exists=True)
    check_resources(
        desired_resources,
        resource_count,
        expected_resource_names=expected_resources_names,
    )


@step("check that resource {resource_name} has parameters with key prefix {key}")
def check_resource_parameters_with_key_prefix(ctx: Context, resource_name: str, key: str) -> None:
    # logger.info(f"check the resource {resource_name} parameters under key {key}:")

    resource = get_resource_from_context(
        ctx, resource_name, assert_exists=True)

    for row in ctx.table:
        param_name = row["param name"]
        param_value = row.get("param value")

        if key:
            param_name = f"{key}.{param_name}"

        # TODO: Have support for operators like {regex} or {contains}
        assert_resource_has_entry(
            resource_name, resource, param_name, expected=param_value
        )


@step("check that resource {resource_name} has parameters")
def check_resource_parameters(ctx: Context, resource_name: str) -> None:
    # logger.info(f"check the resource {resource_name} parameters:")
    check_resource_parameters_with_key_prefix(ctx, resource_name, key="")


@step(
    "check that resource {resource_name} does not have parameters with key prefix {key}"
)
def check_resource_missing_parameters_with_key_prefix(ctx: Context, resource_name: str, key: str) -> None:
    # logger.info(f"check the resource {resource_name} parameters under key {key}:")

    resource = get_resource_from_context(
        ctx, resource_name, assert_exists=True)

    for row in ctx.table:
        param_name = row["param name"]

        if key:
            param_name = f"{key}.{param_name}"

        assert_has_not_resource_entry(resource_name, resource, param_name)


@step("check that resource {resource_name} does not have parameters")
def check_resource_missing_parameters(ctx: Context, resource_name: str) -> None:
    check_resource_missing_parameters_with_key_prefix(
        ctx, resource_name, key="")


@step("check that resource {resource_name} has array parameters of length")
def check_resource_array_parameters_length(ctx: Context, resource_name: str) -> None:
    # logger.info(f"check that resource {resource_name} has array parameters of length:")
    resource = get_resource_from_context(
        ctx, resource_name, assert_exists=True)

    for row in ctx.table:
        param_name, array_length = row["param name"], int(row["length"])

        assert_resource_array_param_has_length(
            resource_name, resource, param_name, array_length
        )


@step("check that xr has status parameters")
@step("check that composite has status parameters")
def check_composite_status_parameters(ctx: Context) -> None:
    # Get the xr from context
    desired_xr = get_from_context(
        ctx, CTX_DESIRED_COMPOSITE_FOR_TEST, assert_exists=True)

    for row in ctx.table:
        param_name, param_value = row["param name"], row["param value"]
        param_name = f"status.{param_name}"

        # TODO: Have support for operators like {regex} or {contains}
        assert_resource_has_entry(
            "composite", desired_xr, param_name, expected=param_value
        )


@step(
    "change observed resource {resource_name} with status {new_status} and parameters"
)
def set_resource_status_and_parameters(ctx: Context, resource_name: str, new_status: str) -> None:
    # logger.info(f"set the resource {resource_name} with status parameters: ")
    set_resource_status(ctx, resource_name, new_status)

    # No need to check that resource exists in desired, already guaranteed by set_resource_status
    resource_is_updated_with(ctx, resource_name)


@step("change observed resource {resource_name} with status {new_status}")
def set_resource_status(ctx: Context, resource_name: str, new_status: str) -> None:
    # logger.info(f"set the resource {resource_name} status to {new_status}")
    # set the status based on a map of READY -> all the fields needed in conditions to show the status ready

    key = "status.conditions"
    if str.lower(new_status) == "ready":
        value = create_fake_status_conditions(ready=True, synced=True)
    else:
        value = create_fake_status_conditions(ready=False, synced=False)

    update_resource_params(ctx, resource_name, {key: value})


@step("change observed resource {resource_name} with parameters")
def resource_is_updated_with(ctx: Context, resource_name: str) -> None:
    """Update the resource with parameters from the table

    Arguments:
        ctx {Context} -- behave context
        resource {str} -- resource name

    Raises:
        AssertionError: resource not found in context
    """
    resource_updates = {}
    for row in ctx.table:
        param_name, param_value = row["param name"], row["param value"]
        resource_updates[param_name] = param_value

    update_resource_params(ctx, resource_name, resource_updates)


@given("change following observed resources with status {new_status}")
def following_resources_are_ready(ctx: Context, new_status: str) -> None:
    """
    Update the resources with the given status

    Arguments:
        ctx {Context} -- behave context
        new_status {str} -- new status

    Raises:
        AssertionError: resources not found in context
    """
    resources_names = [row["resource-name"] for row in ctx.table]
    for resource_name in resources_names:
        set_resource_status(ctx, resource_name, new_status)


@given("change all observed resources with status {new_status}")
def all_resources_are_ready(ctx: Context, new_status: str) -> None:
    """
    Update all resources with the given status

    Arguments:
        ctx {Context} -- behave context
        new_status {str} -- new status

    Raises:
        AssertionError: no desired resources found in context
    """
    observed_resources = get_from_context(
        ctx, CTX_OBSERVED_RESOURCES, assert_exists=True)
    for resource_name in observed_resources.keys():
        set_resource_status(ctx, resource_name, new_status)


@step("claim is applied wrong")
def render_wrong(ctx: Context) -> None:
    # logger.info("render claim wrong")
    assert False


@step("log desired resources")
def log_desired_resources(ctx: Context) -> None:
    logger.info("desired resources")
    # log to stdout and attach to allure step
    # TODO


@step("fail here")
def fail_scenario(ctx: Context) -> None:
    assert False


# def compare_resources(expected_resources, desired_resources, compare_names_only: bool = False):
#     """Compare resources
#
#     Arguments:
#         expected_resources {dict} -- expected resources
#         desired_resources {dict} -- desired resources
#
#     Keyword Arguments:
#         compare_names_only {bool} -- compare only the names of the resources (default: {False})
#
#     Raises:
#         AssertionError: resources are not equal
#     """
#     assert_that(desired_resources, is_not(none()), f"no desired resources found")
#
#     desired_resources_names = list(desired_resources.keys())
#     assert_that(len(desired_resources_names), equal_to(
#         len(expected_resources)), f"expected {len(expected_resources)} resources, got {len(desired_resources_names)}: {desired_resources_names}")
#
#     for r in desired_resources_names:
#         if compare_names_only:
#             assert_that(r in expected_resources, f"{r} not in expected desired resources {expected_resources}. Got desired resources are {desired_resources_names}")
#         else:
#             assert_that(desired_resources[r], equal_to(expected_resources[r]), f"resource {r} not equal")
