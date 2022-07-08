"""Shared utility functions."""
import os
import re
import shlex
import shutil
import sys
import subprocess
import tempfile

VERSION = '2.4.0-SNAPSHOT 2022-02-22'

DEFAULT_DB_URL = "${environment.METRICS_DB_URL}"
DEFAULT_DB_USERNAME = "${environment.METRICS_DB_USERNAME}"
DEFAULT_DB_PASSWORD = "${environment.METRICS_DB_PASS}"

OS_IMAGE = {"rhel7": "registry.access.redhat.com/rhel7:latest",
            "centos7": "centos:7"}

IMAGE_PATTERN = re.compile(r"^(?:(?=[^:\/]{1,253})(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*"
                           "(?::[0-9]{1,5})?/)?((?![._-])(?:[a-z0-9._-]*)(?<![._-])(?:/(?![._-])[a-z0-9._-]*"
                           "(?<![._-]))*)(?::(?![.-])[a-zA-Z0-9_.-]{1,128})?$")

COMMON_SCRIPTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Dockerfiles", "common"))


def banner(msg):
    """Prints a banner message in green."""
    print("""\033[1m\033[32m
===============================================================================
%s
===============================================================================\n\033[0m""" % msg)


def fail(msg, errorCode=1):
    """Prints an error message in red."""
    print("""\033[91m
=====================================ERROR=====================================
%s
===============================================================================\n\033[0m""" % msg)
    sys.exit(errorCode)


def isValidImageName(name):
    """Returns True if name is a valid Docker idenfitier, False otherwise."""
    if name is None:
        return False
    return IMAGE_PATTERN.match(name) is not None


def copy(src, dest):
    """Copies file or directory from src to dest, exits if src does not exist."""
    print("Copying: %s to %s" % (src, dest))
    if not os.path.exists(src):
        fail("\nSource file '%s' does not exist, exiting" % src)
    if os.path.isdir(src):
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def deleteFile(fname, ignoreErrors=True):
    """Deletes specified file, exits if error thrown and ignoreErrors=False."""
    print("Deleting: %s" % fname)
    try:
        os.remove(fname)
    except OSError as e:
        if not ignoreErrors:
            fail("\nFailed to delete file '%s': %s" % (fname, e))


def docker(cmd, args=None, failOnError=True, stdout=None, stderr=subprocess.STDOUT):
    """Executes a Docker command and returns the result code."""
    if args is None:
        args = []
    banner(" ".join(["docker", cmd] + args))

    proc = subprocess.Popen(["docker", cmd] + args, stdout=stdout, stderr=stderr)
    proc.wait()

    if proc.returncode != 0 and failOnError:
        raise Exception("Command failed. Exit status: %s" % proc.returncode)
    else:
        return proc.returncode


def dockerRm(container, options=None, failOnError=True):
    """Removes a Docker container."""
    args = []
    if options:
        args.extend(options)
    args.append(container)
    docker("rm", args=args, failOnError=failOnError)


def dockerRmi(image, options=None, failOnError=True):
    """Removes a Docker image."""
    args = []
    if options:
        args.extend(options)
    args.append(image)
    docker("rmi", args=args, failOnError=failOnError)


def imageExists(imageName):
    """Returns True if Docker image exists, False otherwise."""
    args = [imageName]
    return docker("inspect", args, False, subprocess.PIPE, subprocess.PIPE) == 0


def listDanglingImages():
    """Returns a list of dangling Docker images."""
    imageIds = []
    danglingImageFile = tempfile.NamedTemporaryFile()
    docker("images", ["-q", "-f", "dangling=true"], stdout=danglingImageFile)
    with open(danglingImageFile.name) as f:
        imageIds = f.read()
        imageIds = imageIds.splitlines()
    return imageIds


def removeDanglingImages(imageIdsToKeep):
    """Removes all dangling Docker images, except those listed in imagesToKeep."""
    imageIds = listDanglingImages()
    for imageId in imageIds:
        print("Checking dangling imageId: %s" % imageId)
        if imageId not in imageIdsToKeep:
            try:
                dockerRmi(imageId, ["-f"])
            except Exception as e:
                print("Error removing imageId '%s': %s" % (imageId, e))


def runOpenSslCmd(opensslCmd):
    """Executes an openssl command, returns whatever was written to stdout."""
    opensslCmd = shlex.split(opensslCmd)
    process = subprocess.Popen(opensslCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    errcode = process.returncode
    if errcode != 0:
        if "openssl: command not found" in out:
            fail("openssl not available - install openssl and rerun command")
        else:
            fail("openssl command '%s' failed: %s" % (opensslCmd, err.strip()))
    return out
