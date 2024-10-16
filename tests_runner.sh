#!/bin/bash

# Get the formatter cucumber_json.py from https://github.com/Xray-App/tutorial-python-behave

TARGET_PROJECT_DIR=${1:-.}
TESTS_SUB_DIR=${2:-composition-tests}
TAGS=${3:-""}

LINK_TARGET_PROJECT_DIR=".target_project"

echo "Making sure Crossplane is available $(crossplane version --client)"
echo "Execute the tests from project folder $TARGET_PROJECT_DIR and tests subfolder $TESTS_SUB_DIR"

# check if TAGS is empty
if [ -z "$TAGS" ]; then
    echo "Running all tests"
else
    echo "Running tests with tags $TAGS"
    PARAM_TAGS="--tags=$TAGS"
fi

# check if the target_tests already exists and it is a link (if it is, delete it)
[ -L $LINK_TARGET_PROJECT_DIR ] && rm $LINK_TARGET_PROJECT_DIR
ln -sv $TARGET_PROJECT_DIR $LINK_TARGET_PROJECT_DIR

PYTHONPATH=. behave --junit \
    -f allure_behave.formatter:AllureFormatter -o allure_reports \
    -f cucumber_json:PrettyCucumberJSONFormatter -o cucumber_reports/cucumber_report.json \
    -f pretty \
    $PARAM_TAGS \
    $LINK_TARGET_PROJECT_DIR/$TESTS_SUB_DIR
