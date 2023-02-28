#!/bin/sh
set -ex

# Image name
_IMAGE_NAME="ghcr.io/ansys/ensight_dev"

# Remove all dangling images
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
docker image prune -f

# Pull nexus image based on tag
docker pull $_IMAGE_NAME