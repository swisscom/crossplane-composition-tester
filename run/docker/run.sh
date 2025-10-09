#!/bin/bash
echo "==== Create shared network between functions and crossplane-composition-tester component ===="
docker network create crossplane-net

echo "=== Network created ===="

echo "=== Launch functions ==="
echo "=== Launch function-environment-configs ==="
docker run --network crossplane-net -d --name function-environment-configs xpkg.upbound.io/crossplane-contrib/function-environment-configs:v0.1.0 --insecure --address=:9443
echo "=== Launch function-auto-ready ==="
docker run --network crossplane-net -d --name function-auto-ready xpkg.upbound.io/crossplane-contrib/function-auto-ready:v0.3.0 --insecure --address=:9443
echo "=== Launch function-go-templating ==="
docker run --network crossplane-net -d --name function-go-templating xpkg.upbound.io/crossplane-contrib/function-go-templating:v0.7.0 --insecure --address=:9443

echo "Launch crossplane-composition-testser"
echo "Please update the hostPath folder that contains test"
docker run --rm --network crossplane-net -v /home/ubuntu/test/:/app/test/ -v /home/ubuntu/allure-results:/app/allure-results benmalekarim/crossplane-composition-tester:v0.0.1 behave test/composition-tests -f allure_behave.formatter:AllureFormatter -o /app/allure-results -f pretty