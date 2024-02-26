#!/bin/bash

# Get the formatter cucumber_json.py from https://github.com/Xray-App/tutorial-python-behave

TARGET_TEST_DIR=${1:-.}

echo "Making sure Crossplane is available $(crossplane --version)"
echo "Execute the tests from $TARGET_TEST_DIR"

# check if the target_tests already exists and it is a link (if it is, delete it)
[ -d .target_tests ] && rm .target_tests
ln -s $TARGET_TEST_DIR .target_tests

PYTHONPATH=. behave -f allure_behave.formatter:AllureFormatter -o allure_reports \
    -f cucumber_json:PrettyCucumberJSONFormatter -o cucumber_reports/cucumber_report.json \
    -f pretty \
    .target_tests/
