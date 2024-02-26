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
def setup_functions_filepath(ctx: Context):
    """Setup the functions filepath and save it in the context. By convention, the functions file should be at the same
     level as the directory containing all features folders. Also by convention the file is named "functions.yaml"

    Example:
    ├── features
        ├── feature 1
            ├──
            ├──
        ├── feature 2
            ├──
            ├──
        ├── functions.yaml       # Functions File

    Arguments:
        ctx {Context} -- behave context
    """
    all_features_directory = Path(ctx.base_path).parent
    functions_filepath = all_features_directory / "functions.yaml"
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
    # For example "/pkg/feature-1"
    compositions_directory = project_root / "pkg" / feature_directory_name
    ctx.compositions_directory = compositions_directory
    # For example "/pkg/feature-1/composition.yaml"
    ctx.composition_filepath = compositions_directory / "composition.yaml"



def before_feature(context, feature):
    use_fixture(setup_base_path, context, feature)
    use_fixture(setup_functions_filepath, context)
    use_fixture(setup_composition_filepath, context)