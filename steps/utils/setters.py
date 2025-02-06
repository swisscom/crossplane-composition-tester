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

import os
from pathlib import Path

import allure
import yaml
from behave.runner import Context
from benedict import benedict
from hamcrest import assert_that

from steps.utils.constants import DICT_BENEDICT_SEPARATOR
from steps.utils.utils import get_from_context, get_resource_from_context


def prepare_file(ctx: Context, kind: str, filepath: str, load_into_context: bool = False,
                 attach_to_allure: bool = False, load_multiple_resources: bool = False):
    """Check if file exists and load it into context if needed

    Arguments:
        ctx {Context} -- behave context
        kind {str} --  kind of file (claim, composition, etc)
        filepath {str} -- path to file

    Keyword Arguments:
        load_into_context {bool} -- load the file into context (default: {False})
        attach_to_allure {bool} -- attach the file to allure report (default: {False})
        load_multiple_resources {bool} -- load multiple resources from the file (default: {False})

    Raises:
        AssertionError: file does not exist
    """
    filepath = Path(filepath)
    assert_that(os.path.exists(filepath),
                f"{kind} file ({filepath}) does not exist")

    # load the filepath to the resource to the context
    setattr(ctx, f"{kind}_filepath", filepath)

    if load_into_context:
        with open(filepath, mode="r", encoding="utf-8") as file:
            if load_multiple_resources:
                loaded_input = yaml.safe_load_all(file)
                # If input is a list, load it as is into context
                setattr(ctx, kind, loaded_input)
            else:
                loaded_input = yaml.safe_load(file)
                # Else transform it into a benedict dictionary object
                setattr(ctx, kind, benedict(loaded_input,
                        keypath_separator=DICT_BENEDICT_SEPARATOR))

    if attach_to_allure:
        allure.attach.file(
            filepath,
            name=kind,
            attachment_type=allure.attachment_type.TEXT
        )


def update_resource_params(ctx: Context, resource_name: str, resource_updates):
    """Update a resource with params

    Arguments:
        ctx {Context} -- behave context
        resource_name {str} -- resource name
        resource_updates {dict} -- resource updates

    Raises:
        AssertionError: resource does not exist in context
    """
    # assert resource exists in desired
    get_resource_from_context(ctx, resource_name, assert_exists=True)

    updates = get_from_context(ctx, "updates", False)
    if not updates:
        updates = benedict({}, keypath_separator=DICT_BENEDICT_SEPARATOR)
        ctx.updates = updates

    for key, value in resource_updates.items():
        set_resource_param(updates, f"{resource_name}.{key}", value)


def set_resource_param(resource, key: str, value: str):
    """Set a resource parameter

    Arguments:
        resource {dict} -- resource
        key {str} -- key
        value {str} -- value
    """
    keypath = key.replace(".", DICT_BENEDICT_SEPARATOR)

    resource[keypath] = value
