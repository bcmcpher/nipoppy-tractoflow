#!/bin/bash

# build the docker image w/ local Dockerfile
docker build -t bcmcpher/dmri-tractoflow .

# add a version tag
docker tag bcmcpher/dmri-tractoflow bcmcpher/dmri-tractoflow:1.0.0

# push the image to dockerhub to pull for apptainer build
docker push bcmcpher/dmri-tractoflow:1.0.0

# build the apptainer version of the image
apptainer build tractoflow_2.4.2.sif docker://bcmcpher/dmri-tractoflow:1.0.0
