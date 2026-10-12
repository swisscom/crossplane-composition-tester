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
import functools
import re
import subprocess
from pathlib import Path

import allure

from hamcrest import assert_that, equal_to, none, is_not, has_item, any_of, empty, has_length

from steps.utils.utils import get_resource_entry


def _assert_resource_has_key_and_return_value(resource_name, resource, key: str):
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

def assert_resource_has_entry(resource_name, resource, key: str, expected: str = ""):
    """Check that a resource has an entry

    Arguments:
        resource_name {str} -- resource name
        resource {dict} -- resource
        key {str} -- key

    Keyword Arguments:
        expected {str} -- expected value (default: "")

    Raises:
        AssertionError: resource does not have the entry
    """
    value = str(_assert_resource_has_key_and_return_value(
        resource_name, resource, key)).strip()
    # For now, 'expected' is always read from feature file test as a string
    # and 'value' is always read from the yaml (render output) as a string
    # So, we can compare them as strings
    
    if expected is not None:
        expected = expected.strip()
        assert_that(value, equal_to(expected), f"expected resource {resource_name} to have key {key} with value {expected}, but found value {value} instead")

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
    result = _assert_resource_has_key_and_return_value(
        resource_name, resource, key)

    assert_that(result, has_length(
        length), f"expected resource {resource_name} to have key {key} with length {length}, but has length {len(result)} instead")


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
    
@functools.lru_cache(maxsize=None)
def _crossplane_validate_command() -> tuple:
    """Return the validate command of the installed crossplane CLI.

    The command is 'crossplane beta validate' up to CLI v2.2 and 'crossplane resource validate'
    from v2.3 (the CLI moved to the crossplane/cli repository). Both produce the same output.
    """
    probe = subprocess.run(["crossplane", "resource", "validate", "--help"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode == 0:
        return ("crossplane", "resource", "validate")
    return ("crossplane", "beta", "validate")


def crossplane_validate(definition_filepath, resource, must_be_valid: bool = True) -> None:
    """Validate a resource against a definition schema with 'crossplane resource validate'
    (or 'crossplane beta validate' on CLI versions before v2.3).

    Arguments:
        definition_filepath {str} -- path to the definition (XRD) file to validate against
        resource {str} -- path to the resource (e.g. claim/xr) to validate
        must_be_valid {bool} -- whether the resource is expected to be valid

    Raises:
        AssertionError: definition file not found, resource has no known schema,
                        or validation outcome does not match expectation
    """
    assert_that(
        definition_filepath is not None and Path(str(definition_filepath)).exists(),
        f"definition file not found: {definition_filepath} "
        "(use 'input definition <file>' or ensure definition.yaml exists in the pkg directory)"
    )

    args = [*_crossplane_validate_command(), "--verbose", str(definition_filepath), str(resource)]
    try:
        out = subprocess.check_output(args, universal_newlines=True, stderr=subprocess.STDOUT)
        valid = True
    except subprocess.CalledProcessError as proc_exc:
        out = proc_exc.output
        valid = False

    allure.attach(
        out,
        name="validation output",
    )

    # 'crossplane validate' exits 0 when a resource has no schema in the given extensions,
    # which would silently pass 'valid' checks (e.g. when the definition path is wrong).
    # No verdict is possible in that case, so fail loudly instead.
    # NOTE: This guard targets the output format of crossplane CLI v2.x:
    #   "Total N resources: M missing schemas, X success cases, Y failure cases"
    # If an upgrade changes this format, the assertion below will fail loudly rather than pass silently.
    total_line = re.search(r"Total \d+ resources:", out)
    assert_that(total_line is not None,
                f"crossplane validate did not produce a summary line — CLI output may have changed or the command failed:\n{out}")
    missing_schemas = re.search(r"(\d+) missing schemas", out)
    assert_that(missing_schemas is None or int(missing_schemas.group(1)) == 0,
                f"no schema found for the resource, cannot validate it (is the definition file correct?):\n{out}")

    if must_be_valid:
        assert_that(valid, f"expected validation to succeed, but it failed:\n{out}")
    else:
        assert_that(not valid, f"expected validation to fail, but it succeeded:\n{out}")
