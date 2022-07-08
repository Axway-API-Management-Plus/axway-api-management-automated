#!/usr/bin/env python3
"""Builds a Docker image for an Admin Node Manager."""
import argparse
import os
import shutil
import sys
import time

from utils.utils import VERSION, DEFAULT_DB_URL, DEFAULT_DB_USERNAME, DEFAULT_DB_PASSWORD, COMMON_SCRIPTS_PATH, \
                        copy, deleteFile, docker, fail, imageExists, isValidImageName, listDanglingImages, \
                        removeDanglingImages

# Dockerfile location
LOCAL_DOCKER_PATH = os.path.join(os.path.dirname(__file__), "Dockerfiles", "emt-nodemanager")


def _parseArgs():
    parser = argparse.ArgumentParser(
        description="Builds a Docker image for the Admin Node Manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples\n"
                "--------\n"
                "# Create ANM image using default domain cert and admin user\n"
                "./build_anm_image.py --default-cert --default-user\n\n"
                "# Create ANM image using specified image name, domain cert, key and admin user\n"
                "./build_anm_image.py --out-image=my-domain-anm:0.0.1 \\\n"
                "    --domain-cert=certs/mydomain/mydomain-cert.pem \\\n"
                "    --domain-key=certs/mydomain/mydomain-key.pem \\\n"
                "    --domain-key-pass-file=/tmp/pass.txt \\\n"
                "    --anm-username=gwadmin \\\n"
                "    --anm-pass-file=/tmp/pass1.txt"))

    parser._action_groups.pop()
    grp1 = parser.add_argument_group("general arguments")
    grp1.add_argument("--version", action="version", version=VERSION,
                      help="Show version information and exit.")
    grp1.add_argument("--parent-image", dest="parentImage", default="apigw-base:latest",
                      help="Name and version of parent Docker image. Must have been generated with "
                      "build_base_image.py (default: apigw-base:latest).")
    grp1.add_argument("--out-image", dest="outImage", default="admin-node-manager:latest",
                      help="Name and version for the generated Docker image (default: admin-node-manager:latest).")
    grp1.add_argument("--anm-username", dest="anmUsername", default="admin",
                      help="Admin username for the API Gateway Manager UI (default: admin).")
    grp1.add_argument("--anm-pass-file", dest="anmPassFile",
                      help="File containing admin password for the API Gateway Manager UI.")
    grp1.add_argument("--fed", dest="fed",
                      help="Location of a FED file containing Admin Node Manager configuration.")
    grp1.add_argument("--fed-pass-file", dest="fedPassFile",
                      help="File containing passphrase for the Admin Node Manager's FED file.")
    grp1.add_argument("--license", dest="license",
                      help="License file. Not required to start Admin Node Manager, but may be required for "
                      "optional features such as FIPS mode.")
    grp1.add_argument("--merge-dir", dest="mergeDir",
                      help="Path to a local directory called 'apigateway' that follows the directory structure "
                      "of an API Gateway installation. This is merged into the Admin Node Manager image, and can "
                      "contain custom configuration, JAR files, etc.")
    grp1.add_argument("--healthcheck", dest="healthcheck", action="store_true", default=False,
                      help="Add /healthcheck path on the ANM management port. This can be polled by a load balancer "
                      "to determine if the ANM is running.")

    grp2 = parser.add_argument_group("security arguments")
    grp2.add_argument("--domain-cert", dest="domainCert",
                      help="Location of the domain cert file (e.g., certs/mydomain/mydomain-cert.pem).")
    grp2.add_argument("--domain-key", dest="domainKey",
                      help="Location of the domain private key file (e.g., certs/mydomain/mydomain-key.pem).")
    grp2.add_argument("--domain-key-pass-file", dest="domainKeyPassFile",
                      help="File containing passphrase for the domain private key.")
    grp2.add_argument("--fips", dest="fips", action="store_true", default=False,
                      help="Start Admin Node Manager in FIPS mode.")

    grp3 = parser.add_argument_group("metrics arguments")
    grp3.add_argument("--metrics", dest="metrics", action="store_true", default=False,
                      help="Enable metrics processing in the Admin Node Manager. Remember to provide "
                      "a JDBC driver to connect to the metrics database.")
    grp3.add_argument("--metrics-db-url", dest="metricsDbUrl", default=DEFAULT_DB_URL,
                      help="URL of the metrics database, e.g., jdbc:mysql://metricsdb:3306/metrics "
                      "(default: %s)." % DEFAULT_DB_URL)
    grp3.add_argument("--metrics-db-username", dest="metricsDbUsername", default=DEFAULT_DB_USERNAME,
                      help="Username for connecting to the metrics database (default: %s)." % DEFAULT_DB_USERNAME)
    grp3.add_argument("--metrics-db-pass-file", dest="metricsDbPassFile",
                      help="File containing password for connecting to the metrics database. "
                      "If not specified, default password is '%s'." % DEFAULT_DB_PASSWORD)

    grp4 = parser.add_argument_group("arguments for NON-PRODUCTION environment")
    grp4.add_argument("--default-cert", dest="defaultCert", action="store_true", default=False,
                      help="Use default key and cert generated with 'gen_domain_cert.py --default-cert'. "
                      "If not specified, the three --domain* arguments above must be provided instead.")
    grp4.add_argument("--default-user", dest="defaultUser", action="store_true", default=False,
                      help="Use default admin user for API Gateway Manager UI. Equivalent to specifying "
                      "username=admin, password=changeme.")

    # Print help if script called without arguments
    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    return parser.parse_args()


def _validateArgs():
    _validateGeneralArgs()
    _validateSecurityArgs()
    _validateMetricsArgs()


def _validateGeneralArgs():
    if not args.parentImage:
        fail("Must specify name of parent Docker image.")
    if not isValidImageName(args.parentImage):
        fail("Invalid name for parent Docker image: %s" % args.parentImage)
    if not imageExists(args.parentImage):
        print("WARN: Parent image '%s' does not exist locally, Docker will try to pull "
              "it from remote repository.\n" % args.parentImage)
    if not isValidImageName(args.outImage):
        fail("Invalid name for output Docker image: %s" % args.outImage)

    if args.fed is not None and not os.path.isfile(args.fed):
        fail("FED file does not exist: %s" % args.fed)
    if args.fedPassFile is not None:
        if not os.path.isfile(args.fedPassFile):
            fail("FED passphrase file does not exist: %s" % args.fedPassFile)
        if args.fed is None:
            fail("If you specify a FED passphrase you must also specify a FED file.")

    if args.license is not None and not os.path.isfile(args.license):
        fail("License file does not exist: %s" % args.license)

    if args.mergeDir is not None:
        if not os.path.isdir(args.mergeDir):
            fail("Specified merge directory is not a directory: %s" % args.mergeDir)
        if not args.mergeDir.endswith("apigateway") and not args.mergeDir.endswith("apigateway/"):
            fail("Merge directory must be called 'apigateway'.")

    if args.anmPassFile is not None and not os.path.isfile(args.anmPassFile):
        fail("API Gateway Manager password file does not exist: %s" % args.anmPassFile)
    adminUsersFilePresent = (args.mergeDir is not None and
                             os.path.isfile(os.path.join(args.mergeDir, "conf", "adminUsers.json")))
    if (args.defaultUser, args.anmPassFile is not None, adminUsersFilePresent).count(True) != 1:
        fail("Must specify ONE of --anm-pass-file, --default-user, or --merge-dir "
             "containing file apigateway/conf/adminUsers.json.")


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


def _validateMetricsArgs():
    if args.metrics:
        if args.metricsDbPassFile is not None and not os.path.isfile(args.metricsDbPassFile):
            fail("Metrics database password file does not exist: %s" % args.metricsDbPassFile)
        if args.metricsDbUrl.find("${") == -1 and args.metricsDbUrl[:5] != "jdbc:":
            fail("Invalid metrics database URL '%s': must be a selector or start with 'jdbc:'" % args.metricsDbUrl)
    else:
        args.metricsDbUrl = ""
        args.metricsDbUsername = ""
        args.metricsDbPassFile = None


def _buildANMImage():
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

    passwords = ("DOMAIN_KEY_PASSPHRASE=%s\n"
                 "ANM_PASSPHRASE=%s\n"
                 "ES_PASSPHRASE=%s\n"
                 "METRICS_DB_PASSPHRASE=%s\n"
                 % (_readFromFile(args.domainKeyPassFile, "changeme"),
                    _readFromFile(args.anmPassFile),
                    _readFromFile(args.fedPassFile),
                    _readFromFile(args.metricsDbPassFile, DEFAULT_DB_PASSWORD)))
    with open(os.path.join(resourcePath, "config.props"), 'w') as f:
        f.write(passwords)

    copy(args.domainCert, os.path.join(resourcePath, "domaincert.pem"))
    copy(args.domainKey, os.path.join(resourcePath, "domainkey.pem"))

    if args.license is not None:
        copy(args.license, os.path.join(resourcePath, "lic.lic"))
    if args.fed is not None:
        copy(args.fed, os.path.join(resourcePath, "fed.fed"))
    if args.mergeDir is not None:
        copy(args.mergeDir, os.path.join(resourcePath, "apigateway"))
    copy(os.path.join(os.path.dirname(__file__), "utils", "anm_hc_path.xml"), resourcePath)

    for fname in os.listdir(COMMON_SCRIPTS_PATH):
        copy(os.path.join(COMMON_SCRIPTS_PATH, fname), os.path.join(LOCAL_DOCKER_PATH, "scripts"))


def _readFromFile(fname, defaultValue=""):
    if fname is not None:
        with open(fname) as f:
            return f.read().strip()
    return defaultValue


def _buildImage():
    print("Building Node Manager image: %s" % args.outImage)
    docker("build", ["--no-cache", "--force-rm",
                     "--build-arg", "PARENT_IMAGE=%s" % args.parentImage,
                     "--build-arg", "DOCKER_IMAGE_ID=%s" % args.outImage,
                     "--build-arg", "ANM_USERNAME=%s" % args.anmUsername,
                     "--build-arg", "HEALTHCHECK=%s" % args.healthcheck,
                     "--build-arg", "METRICS_DB_URL=%s" % args.metricsDbUrl,
                     "--build-arg", "METRICS_DB_USERNAME=%s" % args.metricsDbUsername,
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

    _buildANMImage()
