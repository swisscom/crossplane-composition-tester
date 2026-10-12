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
import tempfile

# Temp files are scoped per process so that multiple behave workers (see parallel_runner.py)
# or concurrent runs on the same machine never overwrite each other's render inputs.
_TMP_DIR = os.path.join(tempfile.gettempdir(), f"xplane-composition-tester-{os.getpid()}")

TMP_OBSERVED_FILE_PATH = os.path.join(_TMP_DIR, "observed.yaml")
TMP_XR_FILE_PATH = os.path.join(_TMP_DIR, "xr.yaml")

CTX_DESIRED_COMPOSITE_FOR_TEST = "xr_for_test"
CTX_DESIRED_RESOURCES = "desired_resources"
CTX_DESIRED_COMPOSITE = "desired_xr"
CTX_OBSERVED_RESOURCES = "observed_resources"
CTX_OBSERVED_COMPOSITE = "observed_xr"

RESOURCES_UPDATES = "updates"
XR_UPDATES = "xr_updates"

CLAIM = "claim"
XR = "xr"
COMPOSITION = "composition"
DEFINITION = "definition"
FUNCTIONS = "functions"
ENVCONFIG = "envconfig"
OBSERVED = "observed"

# The separator that benedict will use for keypaths.
# By default, it should be the dot "." however some keys in the manifests already have dots in their keynames and
# so will raise an error if we use dots. So we choose a special separator that is unlikely to be used in the keynames.
DICT_BENEDICT_SEPARATOR = "->"
