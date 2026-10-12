#!/bin/bash

echo "=== Install functions as deployment and expose them via service ==="
kubectl apply -f functions.yaml

kubectl wait --for=condition=available deployment --all --timeout=300s

echo "=== Launch crossplane-composition-tester job ==="
kubectl apply -f crossplane-composition-tester.yaml

kubectl wait --for=condition=complete job/crossplane-composition-tester --timeout=600s

echo "=== Get logs of the crossplane-composition-tester"
kubectl logs job/crossplane-composition-tester -c crossplane-composition-tester
