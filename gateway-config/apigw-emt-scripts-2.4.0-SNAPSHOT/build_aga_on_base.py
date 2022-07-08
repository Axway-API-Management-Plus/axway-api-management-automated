#!/usr/bin/env python3
"""Builds a Docker image for API Gateway Analytics."""
import argparse
import os
import re
import shutil
import stat
import sys
import time

from utils.utils import OS_IMAGE, VERSION, DEFAULT_DB_URL, DEFAULT_DB_USERNAME, DEFAULT_DB_PASSWORD, \
                        COMMON_SCRIPTS_PATH, copy, deleteFile, docker, fail, imageExists, isValidImageName, \
                        listDanglingImages, removeDanglingImages

# Dockerfile location
LOCAL_DOCKER_PATH = os.path.join(os.path.dirname(__file__), "Dockerfiles", "emt-analytics")

EMAIL_PATTERN = re.compile(r"\S+@\S+\.\S+")


def _parseArgs():
    parser = argparse.ArgumentParser(
        description="Builds a Docker image for API Gateway Analytics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples\n"
                "--------\n"
                "# Create image with default user & DB connection, supply JDBC driver via merge-dir:\n"
                "./build_aga_on_base.py --license=license.lic \\\n"
                "                       --os=centos7 --merge-dir=/tmp/analytics --default-user\n\n"
                "# Create image with specified user and DB connection details, supply JDBC driver via merge-dir:\n"
                "./build_aga_on_base.py --license=license.lic \\\n"
                "                       --os=centos7 --merge-dir=/tmp/analytics \\\n"
                "                       --analytics-username=user1 --analytics-pass-file=/tmp/pass.txt \\\n"
                "                       --metrics-db-url=jdbc:mysql://metricsdb:3306/metrics \\\n"
                "                       --metrics-db-username=root --metrics-db-pass-file=/tmp/dbpass.txt"))

    parser._action_groups.pop()
    grp1 = parser.add_argument_group("general arguments")
    grp1.add_argument("--version", action="version", version=VERSION,
                      help="Show version information and exit.")
    grp1.add_argument("--license", required=True, dest="license",
                      help="API Gateway Analytics license.")
    grp1.add_argument("--os", dest="baseOS", choices=OS_IMAGE.keys(),
                      help="Standard OS to use for base image. Either --os or "
                      "--parent-image must be specified.")
    grp1.add_argument("--parent-image", dest="parentImage",
                      help="Name and version of parent Docker image. Must be based on Centos7 or RHEL7.")
    grp1.add_argument("--out-image", dest="outImage", default="apigw-analytics:latest",
                      help="Name and version for the generated Docker image (default: apigw-analytics:latest).")
    grp1.add_argument("--fed", dest="fed",
                      help="Location of a FED file containing API Gateway Analytics configuration. If not "
                      "specified, the default factory FED is used.")
    grp1.add_argument("--fed-pass-file", dest="fedPassFile",
                      help="File containing passphrase for the API Gateway Analytics FED file.")
    grp1.add_argument("--merge-dir", dest="mergeDir",
                      help="Path to a local directory called 'analytics' that follows the directory structure of "
                      "an API Gateway Analytics installation. This is merged into the API Gateway Analytics image, "
                      "and can contain custom configuration, JDBC JAR file, etc.")

    grp2 = parser.add_argument_group("analytics server arguments")
    grp2.add_argument("--analytics-port", dest="analyticsPort", type=int, default=8040,
                      help="The server port that exposes the API Gateway Analytics UI (default: 8040).")
    grp2.add_argument("--analytics-username", dest="analyticsUsername", default="admin",
                      help="Admin username for the API Gateway Analytics UI (default: admin).")
    grp2.add_argument("--analytics-pass-file", dest="analyticsPassFile",
                      help="File containing admin password for the API Gateway Analytics UI.")

    grp3 = parser.add_argument_group("database connection arguments")
    grp3.add_argument("--metrics-db-url", dest="metricsDbUrl", default=DEFAULT_DB_URL,
                      help="URL of the metrics database, e.g., jdbc:mysql://metricsdb:3306/metrics "
                      "(default: %s)." % DEFAULT_DB_URL)
    grp3.add_argument("--metrics-db-username", dest="metricsDbUsername", default=DEFAULT_DB_USERNAME,
                      help="Username for connecting to the metrics database (default: %s)." % DEFAULT_DB_USERNAME)
    grp3.add_argument("--metrics-db-pass-file", dest="metricsDbPassFile",
                      help="File containing password for connecting to the metrics database. "
                      "If not specified, default password is '%s'." % DEFAULT_DB_PASSWORD)

    grp4 = parser.add_argument_group("report generation arguments")
    grp4.add_argument("--reports-dir", dest="reportsDir", default="/tmp/reports",
                      help="Directory into which Analytics reports are stored (default: /tmp/reports).")
    grp4.add_argument("--email-reports", dest="emailReports", action="store_true", default=False,
                      help="Enable report emails. If not specified, report emails are disabled.", )
    grp4.add_argument("--email-to", dest="emailTo", action="append", default=[],
                      help="Destination email address. This argument can be specified multiple times "
                      "for multiple recipients.")
    grp4.add_argument("--email-from", dest="emailFrom",
                      help="Originating email address.")
    grp4.add_argument("--smtp-conn-type", dest="smtpConnType", choices=["NONE", "TLS/SSL", "SSL"], default="NONE",
                      help="SMTP connection type (default: NONE).")
    grp4.add_argument("--smtp-host", dest="smtpHost",
                      help="Hostname of SMTP server.")
    grp4.add_argument("--smtp-port", dest="smtpPort", type=int, default=25,
                      help="Port number of SMTP server (default: 25).")
    grp4.add_argument("--smtp-username", dest="smtpUsername",
                      help="Username used in connection to the SMTP server.")
    grp4.add_argument("--smtp-pass-file", dest="smtpPassFile",
                      help="File containing password for connection to the SMTP server.")
    grp4.add_argument("--cleanup-report", dest="cleanupReport", action="store_true", default=False,
                      help="Delete report file after emailing. If not specified, reports are not "
                      "automatically deleted.")

    grp5 = parser.add_argument_group("arguments for NON-PRODUCTION environment")
    grp5.add_argument("--default-user", dest="defaultUser", action="store_true", default=False,
                      help="Use default user for the API Gateway Analytics UI. Equivalent to specifying "
                      "username=admin, password=changeme.")

    # Print help if script called without arguments
    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    return parser.parse_args()


def _validateArgs():
    _validateGeneralArgs()
    _validateServerAndDbArgs()
    _validateReportArgs()


def _validateGeneralArgs():
    if not os.path.isfile(args.license):
        fail("License file does not exist: %s" % args.license)

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

    if args.fed is not None and not os.path.isfile(args.fed):
        fail("FED file does not exist: %s" % args.fed)
    if args.fedPassFile is not None:
        if not os.path.isfile(args.fedPassFile):
            fail("FED passphrase file does not exist: %s" % args.fedPassFile)
        if args.fed is None:
            fail("If you specify a FED passphrase you must also specify a FED file.")

    if args.mergeDir is not None:
        if not os.path.isdir(args.mergeDir):
            fail("Specified merge directory is not a directory: %s" % args.mergeDir)
        if not args.mergeDir.endswith("analytics") and not args.mergeDir.endswith("analytics/"):
            fail("Merge directory must be called 'analytics'.")


def _validateServerAndDbArgs():
    if args.analyticsPort < 0 or args.analyticsPort > 65535:
        fail("Invalid Analytics port - must be in range 0-65535: %s" % args.analyticsPort)

    if args.defaultUser:
        args.analyticsUsername = "admin"
        args.analyticsPassFile = None
    else:
        if args.analyticsPassFile is None:
            fail("Must specify ONE of --default-user or --analytics-pass-file.")
        if not os.path.isfile(args.analyticsPassFile):
            fail("Analytics password file does not exist: %s" % args.analyticsPassFile)

    if args.metricsDbPassFile is not None and not os.path.isfile(args.metricsDbPassFile):
        fail("Metrics database password file does not exist: %s" % args.metricsDbPassFile)
    if args.metricsDbUrl.find("${") == -1 and args.metricsDbUrl[:5] != "jdbc:":
        fail("Invalid metrics database URL '%s': must be a selector or start with 'jdbc:'" % args.metricsDbUrl)


def _validateReportArgs():
    if args.emailReports:
        if len(args.emailTo) == 0 or None in (args.emailFrom, args.smtpHost, args.smtpUsername, args.smtpPassFile):
            fail("If report emails are enabled, must specify --email-to, --email-from, "
                 "--smtp-host, --smtp-username, --smtp-pass-file.")

        for address in args.emailTo:
            if EMAIL_PATTERN.match(address) is None:
                fail("Invalid --email-to address: %s" % address)
        if EMAIL_PATTERN.match(args.emailFrom) is None:
            fail("Invalid --email-from address: %s" % args.emailFrom)

        if args.smtpPort < 0 or args.smtpPort > 65535:
            fail("Invalid SMTP port - must be in range 0-65535: %s" % args.smtpPort)
        if not os.path.isfile(args.smtpPassFile):
            fail("SMTP password file does not exist: %s" % args.smtpPassFile)
    else:
        args.emailTo = []
        args.emailFrom = ""
        args.smtpHost = ""
        args.smtpPort = 25
        args.smtpUsername = ""
        args.smtpPassFile = None


def _buildAnalyticsImage():
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

    passwords = ("ES_PASSPHRASE=%s\n"
                 "ANALYTICS_PASSPHRASE=%s\n"
                 "METRICS_DB_PASSPHRASE=%s\n"
                 "SMTP_PASSPHRASE=%s\n"
                 % (_readFromFile(args.fedPassFile),
                    _readFromFile(args.analyticsPassFile, "changeme"),
                    _readFromFile(args.metricsDbPassFile, DEFAULT_DB_PASSWORD),
                    _readFromFile(args.smtpPassFile)))
    with open(os.path.join(resourcePath, "config.props"), 'w') as f:
        f.write(passwords)

    copy(args.license, os.path.join(resourcePath, "lic.lic"))
    if args.fed is not None:
        copy(args.fed, os.path.join(resourcePath, "fed.fed"))
    if args.mergeDir is not None:
        copy(args.mergeDir, os.path.join(resourcePath, "analytics"))

    for fname in os.listdir(COMMON_SCRIPTS_PATH):
        copy(os.path.join(COMMON_SCRIPTS_PATH, fname), os.path.join(LOCAL_DOCKER_PATH, "scripts"))


def _readFromFile(fname, defaultValue=""):
    if fname is not None:
        with open(fname) as f:
            return f.read().strip()
    return defaultValue


def _buildImage():
    print("Building API Gateway Analytics image: %s" % args.outImage)
    docker("build", ["--no-cache", "--force-rm",
                     "--build-arg", "PARENT_IMAGE=%s" % args.parentImage,
                     "--build-arg", "DOCKER_IMAGE_ID=%s" % args.outImage,
                     "--build-arg", "ANALYTICS_PORT=%s" % args.analyticsPort,
                     "--build-arg", "ANALYTICS_USERNAME=%s" % args.analyticsUsername,
                     "--build-arg", "METRICS_DB_URL=%s" % args.metricsDbUrl,
                     "--build-arg", "METRICS_DB_USERNAME=%s" % args.metricsDbUsername,
                     "--build-arg", "REPORTS_DIR=%s" % args.reportsDir,
                     "--build-arg", "EMAIL_REPORTS=%s" % args.emailReports,
                     "--build-arg", "EMAIL_TO=%s" % ";".join(args.emailTo),
                     "--build-arg", "EMAIL_FROM=%s" % args.emailFrom,
                     "--build-arg", "SMTP_CONN_TYPE=%s" % args.smtpConnType,
                     "--build-arg", "SMTP_HOST=%s" % args.smtpHost,
                     "--build-arg", "SMTP_PORT=%s" % args.smtpPort,
                     "--build-arg", "SMTP_USERNAME=%s" % args.smtpUsername,
                     "--build-arg", "CLEANUP_REPORT=%s" % args.cleanupReport,
                     "-t", args.outImage,
                     "-f", os.path.join(LOCAL_DOCKER_PATH, "Dockerfile.onbase"),
                     LOCAL_DOCKER_PATH])


def _cleanup():
    shutil.rmtree(os.path.join(LOCAL_DOCKER_PATH, "opt"), ignore_errors=True)
    for fname in os.listdir(COMMON_SCRIPTS_PATH):
        deleteFile(os.path.join(LOCAL_DOCKER_PATH, "scripts", fname))


if __name__ == "__main__":
    args = _parseArgs()
    _validateArgs()

    _buildAnalyticsImage()
