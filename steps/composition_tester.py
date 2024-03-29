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

# from fleet_management_utills import tde_logging

logger = logging.getLogger("xplane-composition-tester logger")
logger.setLevel(logging.INFO)


# use_step_matcher("parse")
# use_step_matcher("cfparse")


# doc: https://behave.readthedocs.io/en/latest/

@given("input compositions directory {compositions_directory}")
def prepare_compositions_directory(ctx: Context, compositions_directory):
    """Prepare working directory with the compositions for the test. This handles the case where compositions
    are located in a different directory than the default /pkg directory.

    Arguments:
        ctx {Context} -- behave context
    """
    ctx.compositions_directory = compositions_directory
    logger.info(f"Current working directory with compositions {compositions_directory}")


@given("input claim is changed with parameters")
def claim_with_params(ctx: Context):
    """
    Update the claim with parameters from the table

    Arguments:
        ctx {Context} -- behave context

    Raises:
        AssertionError: no claim found in context
    """
    claim = get_from_context(ctx, "claim", assert_exists=True)
    claim_updated = claim.copy()
    for row in ctx.table:
        param_name, param_value = row['param name'], row['param value']
        param_value = parse_value_cmd(param_value)
        set_resource_param(claim_updated, param_name, param_value)

    feature_name = ctx.feature.name
    feature_name = feature_name.replace(" ", "_")
    scenario_name = ctx.scenario.name
    scenario_name = scenario_name.replace(" ", "_")
    filename = f"claim_{scenario_name}.yaml"
    filepath = f"{TMP_CLAIMS_FILE_PATH}/{feature_name}/{filename}"
    logger.info(f"dumping updated claim to file {filepath}")
    dump_yaml_to_file(filepath, claim_updated)
    ctx.claim = claim_updated
    ctx.claim_filepath = filepath

    allure.attach.file(
        filepath,
        name=filename,
        attachment_type=allure.attachment_type.TEXT
    )


@given("input claim {claim_file}")
def prepare_claim(ctx: Context, claim_file):
    # logger.info(f"get the claim {claim_file}")

    base_path = getattr(ctx, "base_path", None)
    prepare_file(ctx, CLAIM, f"{base_path}/resources/{claim_file}", load_into_context=True, attach_to_allure=True)


@given('input composition {composition_file}')
def prepare_composition(ctx: Context, composition_file):
    """Retrieve the composition file for the test and check if it exists. By default, the compositions are
    retrieved from a dedicated pkg directory at the root of the project, that mirrors the structure of the test directory
    will all the features.

    Arguments:
        ctx {Context} -- behave context
        composition_file {str} -- composition filename
    """
    # logger.info(f"get test composition {composition_file}")
    prepare_file(ctx, COMPOSITION, f"{ctx.compositions_directory}/{composition_file}", load_into_context=False,
                 attach_to_allure=False)

@given('input functions {functions_file}')
def prepare_functions(ctx: Context, functions_file):
    """Retrieve the functions file for the test and check if it exists. By default, the functions file should be at the
    same level as the parent directory containing all features to test.

    Arguments:
        ctx {Context} -- behave context
        functions_file {str} -- functions filename
    """
    # logger.info(f"get test composition {composition_file}")
    features_directory = ctx.base_path.parent
    prepare_file(ctx, FUNCTIONS, f"{features_directory}/{functions_file}", load_into_context=False,
                 attach_to_allure=False)


@step('crossplane renders the composition')
def render(ctx: Context):
    # get what is needed from the context:
    #  - claim/xr
    #  - composition
    #  - observed resources
    #  - functions - default ones would be in xplane-pkg repo
    #  - context from the environment file - default ones would be in xplane-pkg repo

    # logger.info("rendering composition")
    args = prepare_render_args(ctx, log_input=False)

    out = subprocess.run(args, capture_output=True, text=True)
    assert out.returncode == 0, f"error rendering: {out.stderr}"
    # logger.info(out.stdout)

    # Attach output of render to allure report
    allure.attach(
        out.stdout,
        name="render output",
    )

    read_desired_output_into_context(ctx, out.stdout)


@then("check that no resources are provisioning")
def check_no_resources(ctx: Context):
    # ignore the xr, get only desired resources
    desired_resources = get_from_context(ctx, "desired_resources", assert_exists=False)
    assert_that(desired_resources, any_of(none(), empty()), f"expected no resources, got {desired_resources}")


@step('check that {resource_count:d} resources are provisioning')
def check_resource_count(ctx: Context, resource_count: int):
    # logger.info(f"check that number of resources is {resource_count}")

    # ignore the xr, get only desired resources
    desired_resources = get_from_context(ctx, "desired_resources")
    check_resources(desired_resources, resource_count)


@step('check that {resource_count:d} resources are provisioning and they are')
def check_resource_count_and_names(ctx: Context, resource_count: int):
    # logger.info(f"check that number of resources is {resource_count}")

    expected_resources_names = [row['resource-name'] for row in ctx.table]

    # ignore the xr, get only desired resources
    desired_resources = get_from_context(ctx, "desired_resources")
    check_resources(desired_resources, resource_count, expected_resource_names=expected_resources_names)


@step('check that resource {resource} has parameters')
def check_resource_parameters(ctx, resource):
    # logger.info(f"check the resource {resource} parameters:")

    resource = get_resource_from_context(ctx, resource, assert_exists=True)

    for row in ctx.table:
        param_name, param_value = row['param name'], row['param value']
        assert_has_resource_entry(resource, param_name, value=param_value)


@step('change observed resource {resource} with status {new_status} and parameters')
def set_resource_status_and_parameters(ctx: Context, resource, new_status):
    # logger.info(f"set the resource {resource} with status parameters: ")
    set_resource_status(ctx, resource, new_status)

    # No need to check that resource exists in desired, already guaranteed by set_resource_status
    resource_is_updated_with(ctx, resource)


@step('change observed resource {resource} with status {new_status}')
def set_resource_status(ctx: Context, resource, new_status):
    # logger.info(f"set the resource {resource} status to {new_status}")
    # set the status based on a map of READY -> all the fields needed in conditions to show the status ready

    key = "status.conditions"
    if str.lower(new_status) == "ready":
        value = create_fake_status_conditions(ready=True, synced=True)
    else:
        value = create_fake_status_conditions(ready=False, synced=False)

    update_resource_params(ctx, resource, {key: value})


@step("change observed resource {resource} with parameters")
def resource_is_updated_with(ctx: Context, resource: str):
    """Update the resource with parameters from the table

    Arguments:
        ctx {Context} -- behave context
        resource {str} -- resource name

    Raises:
        AssertionError: resource not found in context
    """
    resource_updates = {}
    for row in ctx.table:
        param_name, param_value = row['param name'], row['param value']
        resource_updates[param_name] = param_value

    update_resource_params(ctx, resource, resource_updates)


@given("change following observed resources with status {new_status}")
def following_resources_are_ready(ctx: Context, new_status: str):
    """
    Update the resources with the given status

    Arguments:
        ctx {Context} -- behave context
        new_status {str} -- new status

    Raises:
        AssertionError: resources not found in context
    """
    resources_names = [row['resource-name'] for row in ctx.table]
    for resource_name in resources_names:
        set_resource_status(ctx, resource_name, new_status)


@given("change all observed resources with status {new_status}")
def all_resources_are_ready(ctx: Context, new_status: str):
    """
    Update all resources with the given status

    Arguments:
        ctx {Context} -- behave context
        new_status {str} -- new status

    Raises:
        AssertionError: no desired resources found in context
    """
    desired_resources = get_from_context(ctx, "desired_resources", assert_exists=True)
    for resource_name in desired_resources.keys():
        set_resource_status(ctx, resource_name, new_status)


@step('claim is applied wrong')
def render_wrong(ctx: Context):
    # logger.info("render claim wrong")
    assert False


@step("log desired resources")
def log_desired_resources(ctx: Context):
    logger.info("desired resources")
    # log to stdout and attach to allure step


@step('fail here')
def fail_scenario(ctx: Context):
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
