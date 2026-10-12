#!/bin/bash
# Start the crossplane composition function containers needed for local testing.
# Uses public images from the Crossplane community on Docker Hub / xpkg.upbound.io.
docker run -d -p 9443:9443 --name function-go-templating-host xpkg.upbound.io/crossplane-contrib/function-go-templating:v0.12.3 "--insecure"
docker run -d -p 9444:9443 --name function-auto-ready-host xpkg.upbound.io/crossplane-contrib/function-auto-ready:v0.7.0 "--insecure"
docker run -d -p 9445:9443 --name function-environment-configs-host xpkg.upbound.io/crossplane-contrib/function-environment-configs:v0.8.0 "--insecure"
