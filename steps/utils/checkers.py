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

from hamcrest import assert_that, equal_to, none, is_not, has_item, any_of, empty, has_length

from steps.utils.utils import get_resource_entry


def assert_resource_has_key_and_return_value(resource_name, resource, key: str):
    """Check that a resource has a key and return the value

    Arguments:
        resource_name {str} -- resource name
        resource {dict} -- resource
        key {str} -- key

    Returns:
        str -- value

    Raises:
        AssertionError: resource does not have the key
    """
    result = get_resource_entry(resource, key)
    assert_that(result, is_not(None),
                f"expected resource {resource_name} to have key {key}")
    return result


def assert_has_resource_entry(resource_name, resource, key: str, value: str = None):
    """Check that a resource has an entry

    Arguments:
        resource_name {str} -- resource name
        resource {dict} -- resource
        key {str} -- key

    Keyword Arguments:
        value {str} -- value (default: {None})

    Raises:
        AssertionError: resource does not have the entry
    """
    result = str(assert_resource_has_key_and_return_value(
        resource_name, resource, key))
    if value:
        assert_that(result, equal_to(
            value), f"expected resource {resource_name} to have {key} with value {value}, but found value {result} instead")


def assert_has_not_resource_entry(resource_name, resource, key: str):
    """Check that a resource does not have an entry

    Arguments:
        resource_name {str} -- resource name
        resource {dict} -- resource
        key {str} -- key

    Raises:
        AssertionError: resource has the entry
    """
    result = get_resource_entry(resource, key)
    assert_that(result, none(
    ), f"expected resource {resource_name} to not have key {key}. Found {key}:{result} instead")


def assert_resource_array_param_has_length(resource_name, resource, key: str, length: int):
    """Check that a resource array parameter has the expected length

    Arguments:
        resource_name {str} -- resource name
        resource {dict} -- resource
        key {str} -- key
        length {int} -- expected length

    Raises:
        AssertionError: resource array parameter does not have the expected length
    """
    result = assert_resource_has_key_and_return_value(
        resource_name, resource, key)

    assert_that(result, has_length(
        length), f"expected resource {resource_name} to have {key} with length {length}, but has length {len(result)} instead")


def check_resources(desired_resources, resource_count: int, expected_resource_names: list[str] = None):
    """Check that the number of resources is as expected and that the names are as expected.

    Arguments:
        desired_resources {dict} -- desired resources
        resource_count {int} -- expected number of resources

    Keyword Arguments:
        resource_names {list[str]} -- expected names of the resources (default: {None})

    Raises:
        AssertionError: number of resources is not as expected
        AssertionError: names of resources are not as expected
    """
    assert_that(desired_resources, is_not(none()),
                f"no desired resources found")
    desired_resources_names = list(desired_resources.keys())
    assert_that(len(desired_resources), equal_to(
        resource_count),
        f"expected {resource_count} resources, got {len(desired_resources_names)}: {desired_resources_names}")

    if expected_resource_names:
        assert_that(len(expected_resource_names), equal_to(resource_count), 
                f"expected number of resources ({resource_count}) does not match the number of resources names provided in table ({len(expected_resource_names)})")
        for r in desired_resources_names:
            assert_that(expected_resource_names, has_item(r),
                        f"{r} not in expected desired resources {expected_resource_names}. Got desired resources {desired_resources_names}")


def check_resources_are_empty(resources):
    assert_that(
        resources,
        any_of(none(), empty()),
        f"expected no resources, got {resources}",
    )

# @step('composite is {status}')
# def check_composite_status(ctx: Context, status):
#     logger.info("check that composite status is {status}")
#     # if there are differences, show them
#     xr = getattr(ctx, "desired_xr", None)
#     assert xr is not None, f"No desired xr"
#
#     xr_status = xr.get("status")
#     assert xr_status is not None, f"expected xr status to be {status}, but no status found"
#
#     conditions = xr_status.get("conditions", [])
#     ready_condition = [
#         cond for cond in conditions if cond.get("type") == "Ready"]
#     assert len(
#         ready_condition) > 0, f"expected xr status to be {status}, but no ready condition status found"
#
#     ready_condition = ready_condition[0]
#     if str.lower(status) == "ready":
#         assert ready_condition[
#                    "status"] == "True", f"expected xr status to be {status}, but found not Ready"
#     if str.lower(status) == "not ready":
#         assert ready_condition[
#                    "status"] == "False", f"expected xr status to be {status}, but found Ready"
