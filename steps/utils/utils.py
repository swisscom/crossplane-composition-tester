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

import collections.abc
import os
import logging
import re
from pathlib import Path

import yaml
from behave.runner import Context
from benedict import benedict
from hamcrest import assert_that, none, is_not

from steps.utils.constants import (
    DICT_BENEDICT_SEPARATOR,
    TMP_OBSERVED_FILE_PATH,
    OBSERVED,
    ENVCONFIG,
    CTX_DESIRED_RESOURCES,
    CTX_DESIRED_COMPOSITE)

logger = logging.getLogger("xplane-composition-tester logger")
logger.setLevel(logging.INFO)


def create_fake_status_conditions(ready=False, synced=True):
    """Create fake status conditions

    Keyword Arguments:
        ready {bool} -- ready status (default: {False})
        synced {bool} -- synced status (default: {True})

    Returns:
        list -- list of status conditions
    """
    ready_condition = {
        "lastTransitionTime": "2023-11-24T15:29:59Z",
        "reason": "Available" if ready else "Unavailable",
        "status": "True" if ready else "False",
        "type": "Ready",
    }

    synced_condition = {
        "lastTransitionTime": "2023-11-24T15:29:59Z",
        "reason": "ReconcileSuccess" if synced else "ReconcileError",
        "status": "True" if synced else "False",
        "type": "Synced",
    }
    return [ready_condition, synced_condition]


def prepare_render_args(ctx: Context, log_input: bool = False):
    """Prepare crossplane render command arguments.

    We identify 3 cases:
    1. We need to run render with no observed state (e.g when we run the claim for the first time)
    2. We need to run render with an observed state which is provided in the context from a dedicated step.
    3. We need to run render with an observed state which is the desired resources from the context plus the updates from dedicated steps.

    Arguments:
        ctx {Context} -- behave context

    Keyword Arguments:
        log_input {bool} -- log the input (the observed resources)  to render (default: {False})

    Returns:
        list -- crossplane render command arguments
    """
    iteration_id = get_iteration_id(ctx)
    # logger.info(f"uid is {uid}")
    
    if log_input:
        dump_yaml_to_file(f"dump/{iteration_id}-in-xr.yaml", ctx.claim)
        
    observed_file = getattr(ctx, f"{OBSERVED}_filepath", None)
    observed_resources = getattr(ctx, CTX_DESIRED_RESOURCES, None)
    # logger.info(f"observed file is {observed_file}")
    # logger.info(f"observed resources are {observed_resources}")
    
    envconfig_arg = ctx.envconfig_filepath

    # Check if we need to run render without an observed state
    if not observed_file and not observed_resources:
        return ["crossplane", "render", ctx.claim_filepath,
                ctx.composition_filepath, ctx.functions_filepath, "-e", envconfig_arg]
        
    if observed_file:
        # use the observed file for one render round
        delattr(ctx, f"{OBSERVED}_filepath")

    else:
        # prepare observed file from the desired resources

        if os.path.exists(TMP_OBSERVED_FILE_PATH):
            # Cleanup current temp file
            os.remove(TMP_OBSERVED_FILE_PATH)

        # First get the desired resources that will act as observed resources to the next render round
        assert observed_resources is not None, f"No resources found in context"

        if log_input:
            dump_yaml_to_file(f"dump/{iteration_id}-in-observed-from-previous-desired.yaml", observed_resources)

        # Merge the observed with the updates accumulated so far
        updates = getattr(ctx, "updates", None)
        if updates:
            if log_input:
                dump_yaml_to_file(f"dump/{iteration_id}-in-changes-from-steps.yaml", updates)

            for resource in ctx.updates:
                if resource in observed_resources:
                    deep_update(observed_resources[resource], ctx.updates[resource])

            if log_input:
                dump_yaml_to_file(f"dump/{iteration_id}-in-observed.yaml", observed_resources)

        # Then dump the observed onto a temp file
        # logger.info(f"running with observed resources {observed_resources}")
        dump_yaml_to_file(TMP_OBSERVED_FILE_PATH,
                          observed_resources.values(), dump_multiple_resources=True)
        observed_file = TMP_OBSERVED_FILE_PATH

    # run the renderer with the observed file as input
    return ["crossplane", "render", ctx.claim_filepath,
            ctx.composition_filepath, ctx.functions_filepath, "-e", envconfig_arg, "-o", observed_file]


def get_from_context(ctx: Context, attr: str, assert_exists: bool = True):
    """Get an attribute from context

    Arguments:
        ctx {Context} -- behave context
        attr {str} -- attribute name

    Keyword Arguments:
        assert_exists {bool} -- assert that the attribute exists (default: {True})

    Raises:
        AssertionError: attribute does not exist

    Returns:
        object -- attribute value
    """
    attr_value = getattr(ctx, attr, None)
    if assert_exists:
        assert_that(attr_value, is_not(none()), f"no {attr} found in context")

    return attr_value


def get_resource_from_context(ctx: Context, resource_name: str, assert_exists: bool = True):
    """
    Get a resource from context

    Arguments:
        ctx {Context} -- behave context
        resource_name {str} -- resource name

    Keyword Arguments:
        assert_exists {bool} -- assert that the resource exists (default: {True})

    Raises:
        AssertionError: resource does not exist in context
    """
    # Get the resource from context
    desired_resources = get_from_context(
        ctx, CTX_DESIRED_RESOURCES, assert_exists=True)
    desired_resource = desired_resources.get(resource_name)
    if assert_exists:
        assert_that(desired_resource, is_not(none()),
                    f"resource {resource_name} not found in desired resources {desired_resources.keys()}")
    return desired_resource


def get_resource_entry(resource, key: str, default=None):
    """Get a resource entry

    Arguments:
        resource {dict} -- resource
        key {str} -- key

    Returns:
        [type] -- entry value
    """
    # Replace dots with the custom DICT_BENEDICT_SEPARATOR to access nested keys
    # Except if the dot is escaped to not replace them in keys with dots (e.g. crossplane.io/claim-name)
    keypath = re.sub(r'(?<!\\)\.', DICT_BENEDICT_SEPARATOR, key)
    # Remove the escape character from the escaped dots if any
    keypath = keypath.replace(r'\.', '.')

    return resource.get(keypath, default)

def save_rendered_output(ctx: Context, render_output: str):
    """Save the render output into a file

    Arguments:
        ctx {Context} -- behave context
        render_ouput {str} -- render output
    """
    iteration_id = get_iteration_id(ctx, new_iteration=False)
    dump_string_to_file(f"dump/{iteration_id}-out-desired.yaml", render_output)    
    
    
def read_desired_output_into_context(ctx: Context, render_output: str):
    """Read the desired state from the render output and save it into context

    Arguments:
        ctx {Context} -- behave context
        render_ouput {str} -- render output

    Raises:
        AssertionError: no desired state found in render output
    """
    desired_state = []
    try:
        # Parse only strings, dicts & lists. Ignore auxiliary types like booleans, integers, floats, etc.
        desired_state = list(yaml.load_all(
            render_output, Loader=yaml.BaseLoader))
    except yaml.YAMLError as e:
        assert_that(False, f"error parsing render output: {e}")

    assert_that(len(desired_state), is_not(
        0), f"render: no desired state output")

    # The first resource from the crossplane render output is always the xr
    desired_xr = desired_state[0]
    setattr(ctx, CTX_DESIRED_COMPOSITE, benedict(
        desired_xr, keypath_separator=DICT_BENEDICT_SEPARATOR))

    desired_resources = desired_state[1:]
    # Create dict from resource names to their payload
    desired_resources = dict(
        [(dr["metadata"]["annotations"]["crossplane.io/composition-resource-name"],
          benedict(dr, keypath_separator=DICT_BENEDICT_SEPARATOR)) for dr in desired_resources]
    )

    setattr(ctx, CTX_DESIRED_RESOURCES, desired_resources)


def parse_value_cmd(value: str):
    """Parse a value command, or return the value if no command returned

    Arguments:
        value {str} -- value

    Returns:
        type -- value
    """
    value = value.strip()
    if value.startswith('\\'):
        value_split = value.split(' ', 1)
        cmd, args = value_split[0], value_split[1]
        if cmd == "\list":
            value = args.split(',')
        else:
            raise NotImplementedError(f"unknown command {cmd}")

    return value


def deep_update(d, u):
    """Deep update dictionaries

    Arguments:
        d {dict} -- dictionary to update
        u {dict} -- dictionary to update from

    Returns:
        dict -- updated dictionary
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def dump_yaml_to_file(filepath, content: str, dump_multiple_resources: bool = False):
    """
    Dump content to file. Creates file if not exists.
    If dump_multiple_resources is True, dump as a list of resources, else dump as a single resource.

    Arguments:
        filepath {str} -- path to file
        content {dict} -- content to dump
        dump_multiple_resources {bool} -- dump multiple resources

    Raises:
        AssertionError: error dumping to file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(exist_ok=True, parents=True)
    try:
        with open(filepath, mode="w+", encoding="utf-8") as file:
            if dump_multiple_resources:
                yaml.safe_dump_all(content, file)
            else:
                yaml.safe_dump(content, file)
    except yaml.YAMLError as e:
        assert_that(False, f"error dumping to file: {e}")

def dump_string_to_file(filepath, content: str):
    """
    Dump content to file. Creates file if not exists.

    Arguments:
        filepath {str} -- path to file
        content {dict} -- content to dump

    Raises:
        AssertionError: error dumping to file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(exist_ok=True, parents=True)
    
    try:
        with open(filepath, mode="w+", encoding="utf-8") as file:
            file.write(content)
    except Exception as e:
        assert_that(False, f"error dumping to file: {e}")

def get_iteration_id(ctx: Context, new_iteration: bool = True):
    """Get an iteration id from context.

    Arguments:
        ctx {Context} -- behave context

    Returns:
        int -- iteration id
    """
    iteration_id = getattr(ctx, "iteration_id", None)
    if iteration_id is None:
        iteration_id = 1
        ctx.iteration_id = iteration_id
    elif new_iteration:
        ctx.iteration_id = iteration_id + 1
    return ctx.iteration_id

