#!/usr/bin/env python3
"""Builds a Docker image for an API Gateway."""
import argparse
import os
import re
import shutil
import sys
import time
import tarfile

from utils.utils import VERSION, DEFAULT_DB_URL, DEFAULT_DB_USERNAME, DEFAULT_DB_PASSWORD, COMMON_SCRIPTS_PATH, \
                        copy, deleteFile, docker, fail, imageExists, isValidImageName, listDanglingImages, \
                        removeDanglingImages, runOpenSslCmd

# Dockerfile location
LOCAL_DOCKER_PATH = os.path.join(os.path.dirname(__file__), "Dockerfiles", "emt-gateway")


def _parseArgs():
    parser = argparse.ArgumentParser(
        description="Builds a Docker image for an API Gateway.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples\n"
                "--------\n"
                "# Create API Gateway image using factory FED and default domain cert\n"
                "./build_gw_image.py --license=license.lic --factory-fed --default-cert\n\n"
                "# Create API Manager image using factory FED and default domain cert\n"
                "./build_gw_image.py --license=license.lic --api-manager --default-cert\n\n"
                "# Create API Gateway image using factory FED and specified image name and domain cert\n"
                "./build_gw_image.py --license=license.lic --factory-fed \\\n"
                "    --out-image=my-group:0.0.1 \\\n"
                "    --domain-cert=certs/mydomain/mydomain-cert.pem \\\n"
                "    --domain-key=certs/mydomain/mydomain-key.pem \\\n"
                "    --domain-key-pass-file=/tmp/pass.txt\n\n"
                "# Create image using specified FED, group ID and merge-dir, and default domain cert\n"
                "./build_gw_image.py --license=license.lic --default-cert \\\n"
                "    --fed=my_group.fed --group-id=my-group --merge-dir=/tmp/apigateway\n\n"))

    parser._action_groups.pop()
    grp1 = parser.add_argument_group("general arguments")
    grp1.add_argument("--version", action="version", version=VERSION,
                      help="Show version information and exit.")
    grp1.add_argument("--license", required=True, dest="license",
                      help="API Gateway license.")
    grp1.add_argument("--parent-image", dest="parentImage", default="apigw-base:latest",
                      help="Name and version of parent Docker image. Must have been generated with "
                      "build_base_image.py (default: apigw-base:latest).")
    grp1.add_argument("--out-image", dest="outImage",
                      help="Name and version for the generated Docker image. All containers started from this "
                      "image are part of the same API Gateway group (default: api-gateway-<group-id>:latest).")
    grp1.add_argument("--group-id", dest="groupId", default="DefaultGroup",
                      help="Unique ID for the set of API Gateways started from this image. Permitted characters: "
                      "[A-Za-z0-9_-]. Must start with a letter, max length 32 (default: DefaultGroup).")
    grp1.add_argument("--fed", dest="fed",
                      help="Location of a FED file containing API Gateway configuration.")
    grp1.add_argument("--yaml", dest="yaml",
                      help="Location of a YAML directory or .tar.gz file containing API Gateway configuration.")
    grp1.add_argument("--pol", dest="pol",
                      help="Location of a POL file containing API Gateway configuration. Matching ENV file "
                      "must also be provided.")
    grp1.add_argument("--env", dest="env",
                      help="Location of an ENV file containing environment-specific settings for API Gateway. "
                      " Matching POL file must also be provided.")
    grp1.add_argument("--fed-pass-file", dest="fedPassFile",
                      help="File containing passphrase for the API Gateway's FED/POL file.")
    grp1.add_argument("--yaml-pass-file", dest="yamlPassFile",
                      help="File containing passphrase for the API Gateway's YAML configuration.")
    grp1.add_argument("--merge-dir", dest="mergeDir",
                      help="Path to a local directory called 'apigateway' that follows the directory structure "
                      "of an API Gateway installation. This is merged into the API Gateway image, and can "
                      "contain custom configuration, JAR files, etc.")

    grp2 = parser.add_argument_group("security arguments")
    grp2.add_argument("--domain-cert", dest="domainCert",
                      help="Location of the domain cert file (e.g., certs/mydomain/mydomain-cert.pem).")
    grp2.add_argument("--domain-key", dest="domainKey",
                      help="Location of the domain private key file (e.g., certs/mydomain/mydomain-key.pem).")
    grp2.add_argument("--domain-key-pass-file", dest="domainKeyPassFile",
                      help="File containing passphrase for the domain private key.")
    grp2.add_argument("--fips", dest="fips", action="store_true", default=False,
                      help="Start API Gateway in FIPS mode.")

    grp3 = parser.add_argument_group("arguments for NON-PRODUCTION environment")
    grp3.add_argument("--default-cert", dest="defaultCert", action="store_true", default=False,
                      help="Use default key and cert generated with 'gen_domain_cert.py --default-cert'. "
                      "If not specified, the three --domain* arguments above must be provided instead.")
    grp3.add_argument("--factory-fed", dest="factoryFed", action="store_true", default=False,
                      help="Use default factory FED with samples instead of custom FED.")
    grp3.add_argument("--factory-yaml", dest="factoryYaml", action="store_true", default=False,
                      help="Use default factory YAML configuration with samples.")
    grp3.add_argument("--api-manager", dest="apiManager", action="store_true", default=False,
                      help="Use factory FED with samples and configure API Manager. To start a Gateway "
                      "container, a Cassandra server must be running at address "
                      "'${environment.CASS_HOST}:9042'. Credentials for API Manager UI are "
                      "apiadmin/changeme. For API Manager metrics, a MySQL database should be running "
                      "at address '%s', with username '%s' and password '%s'."
                      % (DEFAULT_DB_URL, DEFAULT_DB_USERNAME, DEFAULT_DB_PASSWORD))

    # Print help if script called without arguments
    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    return parser.parse_args()


def _validateArgs():
    _validateGeneralArgs()
    _validateSecurityArgs()


# Arguments should be explicitly checked for their default values, not just truthy or falsy values
def _validateGeneralArgs():
    if not os.path.isfile(args.license):
        fail("License file does not exist: %s" % args.license)

    if not re.match("^[A-Za-z]{1}[A-Za-z0-9_-]{0,31}$", args.groupId):
        fail("Invalid group ID: '%s'. Permitted characters: [A-Za-z0-9_-]. "
             "Must start with a letter, max length 32." % args.groupId)

    if (args.apiManager, args.factoryFed, args.fed, args.pol, args.factoryYaml, args.yaml) == (
            False, False, None, None, False, None):
        fail("Must specify API Manager, factory FED, FED, POL, factory YAML or YAML configuration.")

    if args.apiManager:
        if (args.factoryFed, args.factoryYaml, args.fed, args.yaml, args.pol, args.env, args.fedPassFile, args.yamlPassFile) != \
                (False, False, None, None, None, None, None, None):
            fail("API Manager cannot be specified in combination with factory FED, Factory YAML, FED, POL, ENV, YAML, "
                 "FED passphrase or YAML passphrase.")
    if args.factoryFed:
        if (args.fed, args.factoryYaml, args.pol, args.env, args.fedPassFile, args.yamlPassFile, args.yamlPassFile) != (None, False, None, None, None, None, None):
            fail("Factory FED cannot be specified in combination with FED, POL, ENV, YAML, FED passphrase or YAML "
                 "passphrase.")
    if args.fed is not None:
        if not os.path.isfile(args.fed):
            fail("FED file does not exist: %s" % args.fed)
        if (args.pol, args.env) != (None, None):
            fail("Either POL and ENV combination or FED is permitted (POL+ENV=FED).")
    if args.pol is not None:
        if not os.path.isfile(args.pol):
            fail("POL file does not exist: %s" % args.pol)
        if args.env is None:
            fail("ENV file must be provided together with POL.")
    if args.env is not None:
        if not os.path.isfile(args.env):
            fail("ENV file does not exist: %s" % args.env)
        if args.pol is None:
            fail("POL file must be provided together with ENV.")
    if args.yaml is not None:
        if not ((os.path.isfile(args.yaml) and (args.yaml.lower().endswith(".tar.gz") or args.yaml.lower().endswith(".tgz")))
                or os.path.isdir(args.yaml)):
            fail("YAML configuration does not exist at %s in folder or tar.gz/.tgz format" % args.yaml)
    if args.fedPassFile is not None:
        if args.yamlPassFile is not None:
            fail("Cannot specify both a YAML passphrase file and a FED passphrase file")
        if not os.path.isfile(args.fedPassFile):
            fail("FED passphrase file does not exist: %s" % args.fedPassFile)
        if (args.fed, args.pol) == (None, None):
            fail("If you specify a FED passphrase you must also specify a FED or POL file.")
    if args.yamlPassFile is not None:
        if not os.path.isfile(args.yamlPassFile):
            fail("YAML passphrase file does not exist: %s" % args.yamlPassFile)
        if args.yaml is None:
            fail("If you specify a YAML passphrase, you must also specify a YAML configuration")
    if args.mergeDir is not None:
        if not os.path.isdir(args.mergeDir):
            fail("Specified merge directory is not a directory: %s" % args.mergeDir)
        if not args.mergeDir.endswith("apigateway") and not args.mergeDir.endswith("apigateway/"):
            fail("Merge directory must be called 'apigateway'.")

    if args.outImage is None:
        args.outImage = "api-gateway-" + args.groupId.lower()
    if not isValidImageName(args.outImage):
        fail("Invalid name for output Docker image: %s" % args.outImage)

    if not args.parentImage:
        fail("Must specify name of parent Docker image.")
    if not isValidImageName(args.parentImage):
        fail("Invalid name for parent Docker image: %s" % args.parentImage)
    if not imageExists(args.parentImage):
        print("WARN: Parent image '%s' does not exist locally, Docker will try to pull "
              "it from remote repository.\n" % args.parentImage)


def _validateSecurityArgs():
    if args.defaultCert:
        if (args.domainCert, args.domainKey, args.domainKeyPassFile) != (None, None, None):
            fail("If you specify --default-cert, cannot also specify --domain-cert, "
                 "--domain-key or --domain-key-pass-file.")

        args.domainCert = "certs/DefaultDomain/DefaultDomain-cert.pem"
        args.domainKey = "certs/DefaultDomain/DefaultDomain-key.pem"
        if not os.path.isfile(args.domainCert):
            fail("Default domain cert does not exist. Run ./gen_domain_cert.py --default-cert")
        if not os.path.isfile(args.domainKey):
            fail("Default domain private key file does not exist. Run ./gen_domain_cert.py --default-cert")
        if args.groupId == "DefaultDomain":
            fail("Group ID and domain ID cannot be the same; both are set to 'DefaultDomain'")
    else:
        if None in (args.domainCert, args.domainKey, args.domainKeyPassFile):
            fail("Must specify --default-cert or all of (--domain-cert, --domain-key, "
                 "--domain-key-pass-file).")
        if not os.path.isfile(args.domainCert):
            fail("Domain cert file does not exist: %s" % args.domainCert)
        if not os.path.isfile(args.domainKey):
            fail("Domain private key file does not exist: %s" % args.domainKey)
        if not os.path.isfile(args.domainKeyPassFile):
            fail("Domain key passphrase file does not exist: %s" % args.domainKeyPassFile)

        result = runOpenSslCmd('openssl x509 -in "%s" -subject -noout -nameopt multiline' % args.domainCert).decode('ascii')
        domainId = re.search(r"commonName *= *(.*)", result, re.MULTILINE).group(1).strip()
        if args.groupId == domainId:
            fail("Group ID and domain ID cannot be the same; both are set to '%s'" % domainId)


def _buildGatewayImage():
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
    # Copy resources to Docker context
    optPath = os.path.join(LOCAL_DOCKER_PATH, "opt")
    if os.path.exists(optPath):
        shutil.rmtree(optPath)
    resourcePath = os.path.join(optPath, "emt_resources")
    os.makedirs(resourcePath)

    passFile = args.fedPassFile
    if args.yamlPassFile is not None:
        passFile = args.yamlPassFile
    passwords = ("DOMAIN_KEY_PASSPHRASE=%s\n"
                 "ES_PASSPHRASE=%s\n"
                 % (_readFromFile(args.domainKeyPassFile, "changeme"),
                    _readFromFile(passFile)))
    with open(os.path.join(resourcePath, "config.props"), 'w') as f:
        f.write(passwords)

    copy(args.license, os.path.join(resourcePath, "lic.lic"))
    if args.fed is not None:
        copy(args.fed, os.path.join(resourcePath, "fed.fed"))
    if args.yaml is not None:
        if args.yaml.lower().endswith(".tar.gz") or args.yaml.lower().endswith(".tgz"):
            with tarfile.open(args.yaml, "r") as targz:
                targz.extractall(os.path.join(resourcePath, "yaml"))
        elif os.path.isdir(args.yaml):
            copy(args.yaml, os.path.join(resourcePath, "yaml"))
        else:
            fail("Provided YAML path is not a directory or .tar.gz/.tgz file: %s" % args.yaml)
    if args.pol is not None:
        copy(args.pol, os.path.join(resourcePath, "pol.pol"))
    if args.env is not None:
        copy(args.env, os.path.join(resourcePath, "env.env"))
    copy(args.domainCert, os.path.join(resourcePath, "domaincert.pem"))
    copy(args.domainKey, os.path.join(resourcePath, "domainkey.pem"))
    if args.mergeDir is not None:
        copy(args.mergeDir, os.path.join(resourcePath, "apigateway"))

    for fname in os.listdir(COMMON_SCRIPTS_PATH):
        copy(os.path.join(COMMON_SCRIPTS_PATH, fname), os.path.join(LOCAL_DOCKER_PATH, "scripts"))


def _readFromFile(fname, defaultValue=""):
    if fname is not None:
        with open(fname) as f:
            return f.read().strip()
    return defaultValue


def _buildImage():
    print("Building API Gateway image: %s" % args.outImage)
    docker("build", ["--no-cache", "--force-rm",
                     "--build-arg", "PARENT_IMAGE=%s" % args.parentImage,
                     "--build-arg", "GROUP_ID=%s" % args.groupId,
                     "--build-arg", "DOCKER_IMAGE_ID=%s" % args.outImage,
                     "--build-arg", "SETUP_APIMGR=%s" % args.apiManager,
                     "--build-arg", "FACTORY_YAML=%s" % args.factoryYaml,
                     "--build-arg", "FIPS_MODE=%s" % args.fips,
                     "-t", args.outImage,
                     "-f", os.path.join(LOCAL_DOCKER_PATH, "Dockerfile"),
                     LOCAL_DOCKER_PATH])


def _cleanup():
    shutil.rmtree(os.path.join(LOCAL_DOCKER_PATH, "opt"), ignore_errors=True)
    for fname in os.listdir(COMMON_SCRIPTS_PATH):
        deleteFile(os.path.join(LOCAL_DOCKER_PATH, "scripts", fname))


if __name__ == "__main__":
    args = _parseArgs()
    _validateArgs()

    _buildGatewayImage()
