"""Configures a Docker container to run API Gateway Analytics."""
from __future__ import with_statement

import calendar
import datetime
import distutils.dir_util
import optparse
import os
import re
import shlex
import sys
import zipfile
import shutil
import analytics
import configutil
import vutil

from esapi import EntityStoreAPI

from java.lang import Throwable

from com.vordel.version import ProductVersion
from com.vordel.archive.fed import DeploymentArchive

ES_PASSPHRASE = "ES_PASSPHRASE"
ANALYTICS_PASSPHRASE = "ANALYTICS_PASSPHRASE"
METRICS_DB_PASSPHRASE = "METRICS_DB_PASSPHRASE"
SMTP_PASSPHRASE = "SMTP_PASSPHRASE"

DISTDIR = vutil.getVDISTDIR()
fedDir = os.path.join(DISTDIR, "conf", "fed")

def _parseArgs():
    parser = optparse.OptionParser()
    parser.add_option("--props", dest="propsFile",
                      help="Properties file containing name=value pairs.")
    parser.add_option("--fed", dest="fedFile",
                      help="The FED to use for this image.")
    parser.add_option("--merge-dir", dest="mergeDir",
                      help="Config directory to merge into analytics directory.")
    parser.add_option("--docker-image-id", dest="dockerImageId",
                      help="Name and version of the Docker image.")
    parser.add_option("--analytics-port", dest="analyticsPort",
                      help="Port number that exposes the API Gateway Analytics API.")
    parser.add_option("--analytics-username", dest="analyticsUsername",
                      help="Username for logging into API Gateway Analytics UI.")
    parser.add_option("--metrics-db-url", dest="metricsDbUrl",
                      help="Metrics database URL.")
    parser.add_option("--metrics-db-username", dest="metricsDbUsername",
                      help="Metrics database username.")
    parser.add_option("--reports-dir", dest="reportsDir",
                      help="Directory for Analytics reports.")
    parser.add_option("--email-reports", dest="emailReports",
                      help="Enable report emails.", )
    parser.add_option("--email-to", dest="emailTo",
                      help="List of destination email addresses, separated by ';'.")
    parser.add_option("--email-from", dest="emailFrom",
                      help="Originating email address.")
    parser.add_option("--smtp-conn-type", dest="smtpConnType", choices=["NONE", "TLS/SSL", "SSL"], default="NONE",
                      help="SMTP connection type.")
    parser.add_option("--smtp-host", dest="smtpHost",
                      help="Hostname of SMTP server.")
    parser.add_option("--smtp-port", dest="smtpPort", type="int",
                      help="Port number of SMTP server.")
    parser.add_option("--smtp-username", dest="smtpUsername",
                      help="SMTP server username.")
    parser.add_option("--cleanup-report", dest="cleanupReport",
                      help="Delete report file after emailing.")

    opts = parser.parse_args()[0]
    opts.emailReports = True if opts.emailReports.lower() in ("1", "true", "yes") else False
    opts.cleanupReport = True if opts.cleanupReport.lower() in ("1", "true", "yes") else False

    return opts


def _loadPassphrases():
    with open(options.propsFile) as f:
        lines = f.readlines()
    passDict = dict(line.strip().split('=', 1) for line in lines if '=' in line)
    if set(passDict.keys()) != set((ES_PASSPHRASE, ANALYTICS_PASSPHRASE, METRICS_DB_PASSPHRASE, SMTP_PASSPHRASE)):
        _fail("Configuration file is missing required properties: %s" % options.propsFile)
    return passDict


def _setup():
    _checkLicense()
    _updateEsPassphrase()
    _extractCustomFedFile()
    _configureMetrics()
    _setAdminUser()
    _setEnvVariables()

    if options.mergeDir is not None and os.path.exists(options.mergeDir):
        print("Merging provided config directory into analytics directory")
        distutils.dir_util.copy_tree(options.mergeDir, DISTDIR)

    open(os.path.join(DISTDIR, "conf", ".IAgreeToTheTermsAndConditionsOfTheEULA"), 'a').close()


def _checkLicense():
    print("Checking license")
    with open(os.path.join(DISTDIR, "conf", "licenses", "lic.lic")) as f:
        s = f.read()

    if not re.search("analytics *= *1", s):
        _fail("Supplied license file is not valid for API Gateway Analytics.")

    matcher = re.search(r"expires *=.*, ([\d]{2}) ([A-Za-z]{3}) ([\d]{4})", s)
    if matcher is not None:
        day, monthStr, year = matcher.group(1), matcher.group(2), matcher.group(3)
        month = list(calendar.month_abbr).index(monthStr)
        expiryDate = datetime.date(int(year), int(month), int(day))
        if expiryDate < datetime.date.today():
            _fail("Supplied license file has expired.")


def _updateEsPassphrase():
    if len(passphrases[ES_PASSPHRASE]) > 0:
        print("Using a custom entity store passphrase")
        confFile = os.path.join(DISTDIR, "system", "conf", "analytics.xml")
        configutil.updateSystemSettings("file:////%s" % confFile, confFile, None, None, None, None,
                                        secret=passphrases[ES_PASSPHRASE])


def _extractCustomFedFile():
    if not os.path.exists(options.fedFile):
        print("Using factory FED for API Gateway Analytics")
        return

    print("Using custom FED file")
    product, fedVersion = _getProductAndFedVersion()
    productLabel = ProductVersion.getLabel()
    print("   FED Product: %s, FED Version: %s, Product: %s" % (product, fedVersion, productLabel))
    fedPrefix, productPrefix = fedVersion[0:3], productLabel[0:3]
    
    if "Reporter" not in product:
        _fail("Provided FED is not an API Gateway Analytics FED.")
    if fedPrefix != productPrefix:
        _fail("FED version %s does not match the product version %s" % (fedPrefix, productPrefix))

    print("Deleting factory configuration")
    shutil.rmtree(fedDir)
    os.mkdir(fedDir)

    print("Extracting FED file")
    try:
        zipFile = zipfile.ZipFile(options.fedFile)
        for member in zipFile.namelist():
            fname = os.path.basename(member)
            if fname and fname.endswith(".xml"):
                print(" - %s" % fname)
                with open(os.path.join(DISTDIR, "conf", "fed", fname), 'w') as f:
                    f.write(zipFile.read(member))
        zipFile.close()
    except (Exception, Throwable), e:
        _fail("Error extracting FED content: %s" % e)


def _getProductAndFedVersion():
    try:
        if os.path.exists(options.fedFile):
            newArchive = DeploymentArchive(options.fedFile)
            es = EntityStoreAPI.wrap(newArchive.getEntityStore(), passphrases[ES_PASSPHRASE])
        else:
            es = _getEntityStore("PrimaryStore")
        productKey = es.getProductKey()
        fedVersion = es.getVersion()
        es.close()
        return productKey, fedVersion
    except (Exception, Throwable), e:
        _fail("Error reading the FED: %s" % e)


def _getEntityStore(storeType):
    fedDir = os.path.join(DISTDIR, "conf", "fed")
    try:
        for fname in os.listdir(fedDir):
            if re.match(storeType + r".*\.xml", fname) is not None:
                es = EntityStoreAPI.create("file:///%s/%s" % (fedDir, fname),
                                           passphrases[ES_PASSPHRASE], {"strictImportSchema": "false"})
                return es
        _fail("Failed to locate %s in directory '%s'" % (storeType, fedDir))
    except (Exception, Throwable), e:
        _fail("Error opening entity store of type %s: %s" % (storeType, e))


def _configureMetrics():
    print("Adding analytics settings to entity store")
    params = [("passphrase", passphrases[ES_PASSPHRASE]),
              ("port", options.analyticsPort),
              ("dburl", options.metricsDbUrl),
              ("dbuser", options.metricsDbUsername),
              ("dbpass", passphrases[METRICS_DB_PASSPHRASE]),
              ("no-dbcheck", None),
              ("generate", None),
              ("guser", options.analyticsUsername),
              ("gpass", passphrases[ANALYTICS_PASSPHRASE]),
              ("gtemp", options.reportsDir),
              ("email" if options.emailReports else "no-email", None),
              ("emailfrom", options.emailFrom),
              ("emailto", options.emailTo),
              ("smtptype", options.smtpConnType),
              ("smtphost", options.smtpHost),
              ("smtpport", options.smtpPort),
              ("smtpuser", options.smtpUsername),
              ("smtppass", passphrases[SMTP_PASSPHRASE]),
              ("cleanup" if options.cleanupReport else "no-cleanup", None)]

    cmd = os.path.join(DISTDIR, "posix", "bin", "configureserver")
    for name, value in params:
        if value is None:
            cmd += ' --%s' % name
        elif value != "":
            cmd += ' --%s="%s"' % (name, value)

    savedArgv = sys.argv
    sys.argv = shlex.split(cmd)
    analytics.main()
    sys.argv = savedArgv


def _setAdminUser():
    print("Updating admin user details")
    try:
        es = _getEntityStore("UserStore")
        entity = es.get("/[UserStore]**/[User]name=admin")
        entity.setStringField("name", options.analyticsUsername)
        entity.setStringField("password", es.encrypt(passphrases[ANALYTICS_PASSPHRASE]))
        es.updateEntity(entity)
        es.close()
    except (Exception, Throwable), e:
        _fail("Error updating admin user details: %s" % e)


def _setEnvVariables():
    venvPath = os.path.join(DISTDIR, "posix", "lib", "venv")
    print("Setting env variables:")
    with open(venvPath, 'a') as f:
        print("   EMT_ENABLED=true")
        f.write("\nexport EMT_ENABLED=true")
        print("   EMT_IMAGE_ID=%s" % options.dockerImageId)
        f.write("\nexport EMT_IMAGE_ID=%s" % options.dockerImageId)


def _fail(msg, errorCode=1):
    """Prints an error message in red."""
    print("""\033[91m
=====================================ERROR=====================================
%s
===============================================================================\n\033[0m""" % msg)
    sys.exit(errorCode)


if __name__ == "__main__":
    print("\nSetting up API Gateway Analytics...\n")
    options = _parseArgs()
    passphrases = _loadPassphrases()
    _setup()
    print("\nAPI Gateway Analytics setup complete.\n")
