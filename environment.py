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

from behave import fixture, use_fixture
from behave.runner import Context


@fixture
def setup_base_path(ctx: Context, feature):
    """Retrieve the base path for the feature file. The base path is the path to the
    feature folder containing the feature file.

    Arguments:
        ctx {Context} -- behave context

    Raises:
        ValueError: no filename attribute found inside feature in context
    """
    filename = getattr(feature, "filename", None)
    if filename is None:
        raise ValueError(f"no filename attribute found inside feature in context")

    base_path = Path(filename).parent
    ctx.base_path = base_path


@fixture
def setup_envconfig_filepath(ctx: Context):
    """Setup the environment config filepath and save it in the context. By convention, the environment config file should be at the same
     level as the directory containing all features folders. Also by convention the file is named "envconfig.yaml"

    Example:
    ├── features
        ├── feature 1
            ├──
            ├──
        ├── feature 2
            ├──
            ├──
        ├── envconfig.json       # Environment Configuration File

    Arguments:
        ctx {Context} -- behave context
    """
    all_features_directory = Path(ctx.base_path).parent
    envconfig_filepath = all_features_directory / "envconfig.yaml"
    
    # Check if file exists
    if envconfig_filepath.exists():
        ctx.envconfig_filepath = envconfig_filepath


@fixture
def setup_functions_filepath(ctx: Context):
    """Setup the functions filepath and save it in the context. By convention, the functions file should be at the same
     level as the directory containing all features folders. Also by convention the file is named "functions.yaml". 

    Example:
    ├── features
        ├── feature 1
            ├──
            ├──
        ├── feature 2
            ├──
            ├──
        ├── functions.yaml             # Default functions File
        |── functions-ci.yaml          # Version of the functions file to run on CI
        

    Arguments:
        ctx {Context} -- behave context
    """
    all_features_directory = Path(ctx.base_path).parent
    # Save the functions folder path in the context
    # By default, functions files are stored in the same directory as the features
    ctx.functions_folder_path = all_features_directory
    if on_ci():
        print("Running on CI!")
        ctx.on_ci = True
        # If running on CI, the default functions file is specified by the environment variable "COMPOSITION_TESTER_FUNCTIONS_FILE"
        ci_functions_file = os.environ[
            "COMPOSITION_TESTER_FUNCTIONS_FILE"
        ]  # e.g. "functions-ci.yaml"
        functions_filepath = all_features_directory / ci_functions_file
    else:
        print("Running locally!")
        ctx.on_ci = False
        # The default functions file used for testing is "functions.yaml"
        functions_filepath = all_features_directory / "functions.yaml"

    # Save the functions file path in the context
    ctx.functions_filepath = functions_filepath


@fixture
def setup_composition_filepath(ctx: Context):
    """Setup the composition path of the current feature and save it in the context. By convention, the compositions
    directory should be in the "pkg" folder at the root of the project. Also by convention the file is named
    "composition.yaml"

    Example:
    ├── composition-tests
        ├── feature 1
            ├──
            ├── feature1.feature
        ├── feature 2
            ├──
            ├── feature2.feature
        ├── functions.yaml
    ├── pkg         # Compositions directory
        ├── feature 1
            ├── composition.yaml
        ├── feature 2
            ├── composition.yaml
    """
    # For example, "feature-1"
    feature_directory_name = ctx.base_path.name
    project_root = Path(ctx.base_path).parent.parent
    ctx.project_root = project_root
    # For example "/pkg/feature-1"
    compositions_directory = project_root / "pkg" / feature_directory_name
    ctx.compositions_directory = compositions_directory
    # For example "/pkg/feature-1/composition.yaml"
    ctx.composition_filepath = compositions_directory / "composition.yaml"

@fixture
def setup_from_environment(ctx: Context):
    """Get the environment variables and set them in the context
    """
    
    ctx.debug_mode = os.environ.get("COMPOSITION_TESTER_DEBUG_MODE", "False").lower() == "true"
    
    
def before_feature(context, feature):
    use_fixture(setup_base_path, context, feature)
    use_fixture(setup_envconfig_filepath, context)
    use_fixture(setup_functions_filepath, context)
    use_fixture(setup_composition_filepath, context)
    use_fixture(setup_from_environment, context)


def on_ci():
    # check special environment variable to determine if running locally or in CI pipeline (e.g. GITLAB_CI)
    return "COMPOSITION_TESTER_FUNCTIONS_FILE" in os.environ
