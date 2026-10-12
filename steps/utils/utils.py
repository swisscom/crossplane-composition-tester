# Copyright 2023 Swisscom (Schweiz) AG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
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
    TMP_XR_FILE_PATH,
    CTX_DESIRED_RESOURCES,
    CTX_DESIRED_COMPOSITE,
    CTX_OBSERVED_COMPOSITE,
    CTX_OBSERVED_RESOURCES,
    RESOURCES_UPDATES,
    XR_UPDATES,
    CTX_DESIRED_COMPOSITE_FOR_TEST)

logger = logging.getLogger("xplane-composition-tester logger")
logger.setLevel(logging.INFO)


def create_fake_status_conditions(ready=False, synced=True):
    """
    Create fake status conditions for testing.

    Args:
        ready (bool): Ready status. Defaults to False.
        synced (bool): Synced status. Defaults to True.

    Returns:
        list[dict]: List of status conditions.
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


def get_dump_path(ctx: Context, filename: str) -> str:
    """
    Return the file path for dumping content.
    If ctx.execution_folder is set, use that; otherwise, fallback to 'dump' in the current working directory.

    Args:
        ctx (Context): Behave context.
        filename (str): Name of the file.

    Returns:
        str: Full path to the dump file.
    """
    if hasattr(ctx, "execution_folder"):
        dump_dir = Path(ctx.execution_folder)
    else:
        dump_dir = Path.cwd() / "dump"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return str(dump_dir / filename)


def prepare_render_args(ctx: Context, log_input: bool = False):
    """
    Prepare arguments for the crossplane render command.

    Handles:
        1. No observed state (first run).
        2. Observed state from context.
        3. Observed state as desired resources plus updates.

    Args:
        ctx (Context): Behave context.
        log_input (bool): Whether to log input files.

    Returns:
        list: Crossplane render command arguments.
    """
    iteration_id = get_iteration_id(ctx)
    desired_xr = get_from_context(ctx, CTX_DESIRED_COMPOSITE, assert_exists=True)

    observed_resources = get_from_context(ctx, CTX_OBSERVED_RESOURCES)
    xr_updates = get_from_context(ctx, XR_UPDATES)
    resource_updates = get_from_context(ctx, RESOURCES_UPDATES)

    render_args = [
        "crossplane", "render", "--include-full-xr", TMP_XR_FILE_PATH,
        ctx.composition_filepath, ctx.functions_filepath
    ]
    
    envconfig_arg = get_from_context(ctx, "envconfig_filepath")
    if envconfig_arg:
        render_args += ["-e", envconfig_arg]

    # Pass the definition to render as --xrd so the XRD's schema defaults (and pruning) are
    # applied to the XR before composing — the same definition file (auto-resolved by
    # convention or overridden by an 'input definition' step) that the validation steps use.
    definition_filepath = get_from_context(ctx, "definition_filepath")
    if definition_filepath and Path(definition_filepath).exists():
        render_args += ["--xrd", str(definition_filepath)]

    render_args += ["--include-context"]
    
    # Clean up temp files
    for path in [TMP_XR_FILE_PATH, TMP_OBSERVED_FILE_PATH]:
        if os.path.exists(path):
            os.remove(path)

    # Apply updates to observed resources if present
    if observed_resources:
        if resource_updates:
            for resource, update in resource_updates.items():
                if resource in observed_resources:
                    deep_update(observed_resources[resource], update)
            if log_input:
                dump_yaml_to_file(get_dump_path(ctx, f"{iteration_id}-in-changes-from-steps.yaml"), resource_updates)
        if log_input:
            dump_yaml_to_file(get_dump_path(ctx, f"{iteration_id}-in-observed.yaml"), observed_resources)

    # Apply updates to XR if present
    if xr_updates:
        deep_update(desired_xr, xr_updates)
        if log_input:
            dump_yaml_to_file(get_dump_path(ctx, f"{iteration_id}-in-xr-changes-from-steps.yaml"), xr_updates)
    if log_input:
        dump_yaml_to_file(get_dump_path(ctx, f"{iteration_id}-in-xr.yaml"), desired_xr)

    # Always write XR to file
    dump_yaml_to_file(TMP_XR_FILE_PATH, desired_xr)

    # If observed resources exist, write observed file and add to args
    if observed_resources:
        observed = [desired_xr] + list(observed_resources.values())
        dump_yaml_to_file(TMP_OBSERVED_FILE_PATH, observed, dump_multiple_resources=True)
        if log_input:
            dump_yaml_to_file(get_dump_path(ctx, f"{iteration_id}-in-observed-from-previous-desired.yaml"), observed_resources)
        return render_args + ["-o", TMP_OBSERVED_FILE_PATH]

    return render_args


def get_from_context(ctx: Context, attr: str, assert_exists: bool = False):
    """
    Get an attribute from context.

    Args:
        ctx (Context): Behave context.
        attr (str): Attribute name.
        assert_exists (bool): Assert that the attribute exists. Defaults to True.

    Raises:
        AssertionError: If attribute does not exist.

    Returns:
        object: Attribute value.
    """
    attr_value = getattr(ctx, attr, None)
    if assert_exists:
        assert_that(attr_value, is_not(none()), f"no {attr} found in context")

    return attr_value


def get_resource_from_context(ctx: Context, resource_name: str, state=CTX_DESIRED_RESOURCES, assert_exists: bool = True):
    """
    Get a resource from context.

    Args:
        ctx (Context): Behave context.
        resource_name (str): Resource name.
        state (str): Context attribute for resources, mainly observed or desired. Defaults to CTX_DESIRED_RESOURCES.
        assert_exists (bool): Assert that the resource exists. Defaults to True.

    Raises:
        AssertionError: If resource does not exist in context.

    Returns:
        dict: Resource entry.
    """
    # Get the resource from context
    desired_resources = get_from_context(
        ctx, state, assert_exists=True)
    desired_resource = desired_resources.get(resource_name)
    if assert_exists:
        assert_that(desired_resource, is_not(none()),
                    f"resource {resource_name} not found in desired resources {desired_resources.keys()}")
    return desired_resource


def get_resource_entry(resource, key: str, default=None):
    """
    Get a resource entry by key, supporting nested keys with custom separator.

    Args:
        resource (dict): Resource dictionary.
        key (str): Key (dot notation supported, use \\. for literal dot).
        default: Default value if key not found.

    Returns:
        Any: Entry value or default.
    """
    # Replace dots with the custom DICT_BENEDICT_SEPARATOR to access nested keys
    # Except if the dot is escaped to not replace them in keys with dots (e.g. crossplane.io/claim-name)
    keypath = to_benedict_keypath(key)
    return resource.get(keypath, default)


def save_rendered_output(ctx: Context, render_output: str):
    """
    Save the render output into a file.

    Args:
        ctx (Context): Behave context.
        render_output (str): Render output.
    """
    iteration_id = get_iteration_id(ctx, new_iteration=False)
    dump_string_to_file(get_dump_path(ctx, f"{iteration_id}-out-desired.yaml"), render_output)


def load_xr_and_resources_into_context(ctx: Context, resources_raw: str, desired=True):
    """
    Load the composite resource and composed resources into context.
    The payload can be either the desired state from render output or an observed state from a prepared file.

    Args:
        ctx (Context): Behave context.
        resources_raw (str): YAML string of resources.
        desired (bool): If True, store as desired as well.

    Raises:
        AssertionError: If no resources are found in the payload.
    """
    # The first resource from the crossplane render output or the observed is always the xr
    # Extract it separately since we use a different yaml load on the xr
    resources_raw_split = resources_raw.strip().split("---")
    xr_raw = resources_raw_split[1] if resources_raw.startswith("---") else resources_raw_split[0]
    try:
        # load the xr twice:
        # 1 - using safe_load to preserve types (for xr validation) and as input to the render
        # 2 - using base loader to load everything as string to run checks on the the xr output 
        xr_for_validation = yaml.safe_load(xr_raw)
        xr_for_test = yaml.load(xr_raw, Loader=yaml.BaseLoader)
        # For the rest of the resources use load with BaseLoader to load everything as strings.
        # Parse only strings, dicts & lists. Ignore auxiliary types like booleans, integers, floats, etc.
        resources = list(yaml.load_all(resources_raw, Loader=yaml.BaseLoader))
    except yaml.YAMLError as e:
        assert_that(False, f"error parsing resources: {e}")

    assert_that(resources, is_not(none()), "no resources found in payload")
    assert_that(len(resources), is_not(0), "no resources found in payload")
    
    # Save the xr in context
    setattr(ctx, CTX_OBSERVED_COMPOSITE, benedict(xr_for_validation, keypath_separator=DICT_BENEDICT_SEPARATOR))
    if desired:
        setattr(ctx, CTX_DESIRED_COMPOSITE, benedict(xr_for_validation, keypath_separator=DICT_BENEDICT_SEPARATOR))
        setattr(ctx, CTX_DESIRED_COMPOSITE_FOR_TEST, benedict(xr_for_test, keypath_separator=DICT_BENEDICT_SEPARATOR))

    # Create dict from resource names to their payload
    composed_resources = {}
    for res in resources[1:]:
        name = res.get("metadata", {}).get("annotations", {}).get("crossplane.io/composition-resource-name")
        if name:
            composed_resources[name] = benedict(res, keypath_separator=DICT_BENEDICT_SEPARATOR)
    setattr(ctx, CTX_OBSERVED_RESOURCES, composed_resources)
    if desired:
        setattr(ctx, CTX_DESIRED_RESOURCES, composed_resources)


def parse_value_cmd(value: str):
    """
    Parse a value command, or return the value if no command is present.

    Args:
        value (str): Value string.

    Returns:
        Any: Parsed value.
    """
    value = value.strip()
    if value.startswith('\\'):
        value_split = value.split(' ', 1)
        cmd = value_split[0].strip('\\')

        if cmd == "nil" or cmd == "null":
            return None

        arg = value_split[1]
        if cmd == 'list':
            value = arg.split(',')
        elif cmd == "bool":
            value = arg == "True" or arg == "true"
        elif cmd == "int":
            value = int(arg)
        else:
            raise NotImplementedError(f"unknown command {cmd}")
    return value

def deep_update(d, u):
    """
    Deep update dictionaries (recursive merge).

    Args:
        d (dict): Dictionary to update.
        u (dict): Dictionary to update from.

    Returns:
        dict: Updated dictionary.
    """
    for key, value in u.items():
        if isinstance(value, collections.abc.Mapping) and isinstance(d.get(key), collections.abc.Mapping):
            # If both are dictionaries, extend the merge recursively
            deep_update(d[key], value)
        elif isinstance(value, list) and isinstance(d.get(key), list):
            # If both are lists, update elements if they differ or append new ones
            d[key] = update_list(d[key], value)
        else:
            # Otherwise, override the value
            d[key] = value
    return d

def update_list(source_list, override_list):
    """
    Update a list in place by applying overrides from another list.

    Args:
        source_list (list): The original list to update.
        override_list (list): The list with new values.

    Returns:
        list: Updated list.
    """
    max_len = max(len(source_list), len(override_list))
    updated_list = source_list[:]

    for i in range(max_len):
        if i < len(override_list):
            if i >= len(updated_list):
                # Append new elements if the source list is shorter
                updated_list.append(override_list[i])
            elif isinstance(updated_list[i], collections.abc.Mapping) and isinstance(override_list[i], collections.abc.Mapping):
                # Recursively update if the item is a dict
                deep_update(updated_list[i], override_list[i])
            else:
                # Replace the element if it differs
                updated_list[i] = override_list[i]
        # Optionally handle additional items from source_list (e.g., preserve)
    return updated_list


def dump_yaml_to_file(filepath, content: str, dump_multiple_resources: bool = False):
    """
    Dump content to file. Creates file if not exists.
    If dump_multiple_resources is True, dump as a list of resources, else dump as a single resource.

    Args:
        filepath (str): Path to file.
        content (dict or list): Content to dump.
        dump_multiple_resources (bool): Dump multiple resources if True.

    Raises:
        AssertionError: If error occurs during dumping.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(exist_ok=True, parents=True)

    def str_presenter(dumper, data):
        if isinstance(data, str) and '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, str_presenter)

    try:
        with open(filepath, mode="w+", encoding="utf-8") as file:
            if dump_multiple_resources:
                yaml.safe_dump_all(content, file, default_flow_style=False, allow_unicode=True, sort_keys=False)
            else:
                yaml.safe_dump(content, file, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except yaml.YAMLError as e:
        assert_that(False, f"error dumping to file: {e}")


def dump_string_to_file(filepath, content: str):
    """
    Dump string content to file. Creates file if not exists.

    Args:
        filepath (str): Path to file.
        content (str): Content to dump.

    Raises:
        AssertionError: If error dumping to file.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(exist_ok=True, parents=True)
    try:
        with open(filepath, mode="w+", encoding="utf-8") as file:
            file.write(content)
    except Exception as e:
        assert_that(False, f"error dumping to file: {e}")


def get_iteration_id(ctx: Context, new_iteration: bool = True):
    """
    Get an iteration id from context.

    Args:
        ctx (Context): Behave context.
        new_iteration (bool): If True, increment iteration. Defaults to True.

    Returns:
        int: Iteration id.
    """
    iteration_id = getattr(ctx, "iteration_id", None)
    if iteration_id is None:
        iteration_id = 1
        ctx.iteration_id = iteration_id
    elif new_iteration:
        ctx.iteration_id = iteration_id + 1
    return ctx.iteration_id


def to_benedict_keypath(keypath: str) -> str:
    """
    Convert a dot-separated keypath to benedict keypath using the custom separator.
    Escaped dots (\\.) are preserved as literal dots.

    Args:
        keypath (str): Dot-separated keypath.

    Returns:
        str: Keypath with custom separator.
    """
    # Replace unescaped dots with the custom separator
    keypath = re.sub(r'(?<!\\)\.', DICT_BENEDICT_SEPARATOR, keypath)
    # Replace escaped dots (\.) with literal dots
    return keypath.replace(r'\.', '.')
