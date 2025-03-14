#!/bin/bash

# build the docker image w/ local Dockerfile
docker build -t bcmcpher/dMRI-tractoflow .

# add a version tag
docker tag bcmcpher/dMRI-tractoflow bcmcpher/dMRI-tractoflow:1.0.0

# push the image to dockerhub to pull for apptainer build
docker push bcmcpher/dMRI-tractoflow:1.0.0

# build the apptainer version of the image
apptainer build dMRI-tractoflow_1.0.0.sif docker://bcmcpher/dMRI-tractoflow:1.0.0
