#!/bin/bash
# Run the example tests (examples/test) fully inside docker: the composition functions and the
# tester share a docker network, so functions.yaml targets the functions by container name.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="crossplane-composition-tester:local"
NETWORK="crossplane-net"

echo "=== Build the crossplane-composition-tester image ==="
docker build -t "$IMAGE" "$REPO_ROOT"

echo "=== Create shared network between the functions and the tester ==="
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

echo "=== Launch functions ==="
trap 'docker rm -f function-go-templating function-auto-ready function-environment-configs >/dev/null 2>&1' EXIT
docker run --network "$NETWORK" -d --rm --name function-go-templating xpkg.upbound.io/crossplane-contrib/function-go-templating:v0.12.3 --insecure --address=:9443
docker run --network "$NETWORK" -d --rm --name function-auto-ready xpkg.upbound.io/crossplane-contrib/function-auto-ready:v0.7.0 --insecure --address=:9443
docker run --network "$NETWORK" -d --rm --name function-environment-configs xpkg.upbound.io/crossplane-contrib/function-environment-configs:v0.8.0 --insecure --address=:9443

echo "=== Run the tests ==="
docker run --rm --network "$NETWORK" \
  -v "$REPO_ROOT/examples/test:/app/test:ro" \
  "$IMAGE" test/composition-tests
