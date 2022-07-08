#!/usr/bin/env python3
"""Builds a base Docker image for API Gateway and Admin Node Manager."""
import argparse
import os
import stat
import sys
import time

from utils.utils import OS_IMAGE, VERSION, copy, docker, fail, imageExists, isValidImageName, \
                        listDanglingImages, removeDanglingImages

# Dockerfile location
LOCAL_DOCKER_PATH = os.path.join(os.path.dirname(__file__), "Dockerfiles", "gateway-base")


def _parseArgs():
    parser = argparse.ArgumentParser(
        description="Builds the base Docker image for API Gateway and Admin Node Manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples\n"
                "--------\n"
                "# Create image based on Red Hat Enterprise Linux 7\n"
                "./build_base_image.py --installer=apigw-installer.run --os=rhel7\n\n"
                "# Create image with specified parent and output image names\n"
                "./build_base_image.py --installer=apigw-installer.run \\\n"
                "                      --parent-image=my-custom-rhel:2.0 --out-image=my-gw-base:1.0"))

    parser._action_groups.pop()
    grp1 = parser.add_argument_group("arguments")
    grp1.add_argument("--version", action="version", version=VERSION,
                      help="Show version information and exit.")
    grp1.add_argument("--installer", dest="installer", required=True,
                      help="Path to API Gateway installer.")
    grp1.add_argument("--os", dest="baseOS", choices=OS_IMAGE.keys(),
                      help="Standard OS to use for base image. Either --os or "
                      "--parent-image must be specified.")
    grp1.add_argument("--parent-image", dest="parentImage",
                      help="Name and version of parent Docker image. Must be based on Centos7 or RHEL7.")
    grp1.add_argument("--user-uid", dest="userUid", default=1000,
                      help="Container user uid.")
    grp1.add_argument("--user-gid", dest="userGid", default=1000,
                      help="Container user gid.")
    grp1.add_argument("--out-image", dest="outImage", default="apigw-base:latest",
                      help="Name and version for the generated Docker image (default: apigw-base:latest).")

    # Print help if script called without arguments
    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    return parser.parse_args()


def _validateArgs():
    if not os.path.isfile(args.installer):
        fail("Installer does not exist: %s" % args.installer)
    if (args.baseOS, args.parentImage).count(None) != 1:
        fail("Must specify one of --os or --parent-image.")
    if not isValidImageName(args.outImage):
        fail("Invalid name for output image: %s" % args.outImage)

    if args.parentImage is not None:
        if not isValidImageName(args.parentImage):
            fail("Invalid name for parent image: %s" % args.parentImage)
        if not imageExists(args.parentImage):
            print("WARN: Parent image '%s' does not exist locally, Docker will try to pull "
                  "it from remote repository.\n" % args.parentImage)
    else:
        args.parentImage = OS_IMAGE[args.baseOS]


def _buildBaseImage():
    danglingImageIds = listDanglingImages()
    try:
        _setup()
        _buildImage()
    except:
        # Allow running container to stop
        time.sleep(3)
        raise
    finally:
        _cleanup()
        removeDanglingImages(danglingImageIds)


def _setup():
    newInstallerPath = os.path.join(LOCAL_DOCKER_PATH, "APIGateway_Install.run")
    copy(args.installer, newInstallerPath)
    # Make sure installer is executable
    st = os.stat(newInstallerPath)
    os.chmod(newInstallerPath, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _buildImage():
    print("Building base API Gateway image: %s\nParent image: %s" % (args.outImage, args.parentImage))
    docker("build", ["--build-arg", "PARENT_IMAGE=%s" % args.parentImage,
                     "--build-arg", "USER_UID=%s" % args.userUid,
                     "--build-arg", "USER_GID=%s" % args.userGid,
                     "-t", args.outImage,
                     "-f", os.path.join(LOCAL_DOCKER_PATH, "Dockerfile"),
                     LOCAL_DOCKER_PATH])


def _cleanup():
    try:
        os.remove(os.path.join(LOCAL_DOCKER_PATH, "APIGateway_Install.run"))
    except OSError:
        pass


if __name__ == "__main__":
    args = _parseArgs()
    _validateArgs()

    _buildBaseImage()
