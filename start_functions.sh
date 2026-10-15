#!/bin/bash
# Start the crossplane composition function containers needed for local testing.
# Uses public images from the Crossplane community registry (xpkg.crossplane.io).
docker run -d -p 9443:9443 --name function-go-templating-host xpkg.crossplane.io/crossplane-contrib/function-go-templating:v0.12.5 "--insecure"
docker run -d -p 9444:9443 --name function-auto-ready-host xpkg.crossplane.io/crossplane-contrib/function-auto-ready:v0.7.0 "--insecure"
docker run -d -p 9445:9443 --name function-environment-configs-host xpkg.crossplane.io/crossplane-contrib/function-environment-configs:v0.8.0 "--insecure"
