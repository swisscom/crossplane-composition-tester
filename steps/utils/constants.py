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

BASE_PATH = f"features"

TMP_OBSERVED_FILE_PATH = "/tmp/observed.yaml"
TMP_CLAIMS_FILE_PATH = "/tmp/claims"

CLAIM = "claim"
COMPOSITION = "composition"
FUNCTIONS = "functions"

# The separator that benedict will use for keypaths.
# By default, it should be the dot "." however some keys in the manifests already have dots in their keynames and
# so will raise an error if we use dots. So we choose a special separator that is unlikely to be used in the keynames.
DICT_BENEDICT_SEPARATOR = "->"
