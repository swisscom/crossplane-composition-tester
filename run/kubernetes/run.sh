#!/bin/bash

echo "=== Install functions as deployment and expose them via service ==="
kubectl apply -f functions.yaml

echo "=== Launch crossplane-composition-testser job ==="
kubectl apply -f crossplane-composition-tester.yaml

kubectl wait --for=condition=complete job -l app=crossplane-composition-tester

POD_NAME=$(kubectl get pods -l app=crossplane-composition-tester -oname)

echo "=== Get logs of the crossplane-composition-tester"
kubectl logs $POD_NAME