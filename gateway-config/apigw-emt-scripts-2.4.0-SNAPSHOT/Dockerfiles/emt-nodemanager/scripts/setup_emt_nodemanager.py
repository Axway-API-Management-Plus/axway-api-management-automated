"""Configures a Docker container to run an Admin Node Manager."""
from __future__ import with_statement

import calendar
import datetime
import distutils.dir_util
import optparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import zipfile

import cert
import configutil
import mdenums
import vutil

from diskinstancemanager import DiskInstanceManager
from esapi import EntityStoreAPI
from mdhost import HostManager, FirstHostManager
from mdparams import MetricsParams, UpgradeTopologyParams
from metricsmanager import MetricsManager
from openssl import OpenSSLUtil

from java.io import ByteArrayOutputStream, PrintStream
from java.lang import System, String, Throwable

from com.vordel.api.connection import CertificateHandler
from com.vordel.api.domain.controller import FipsController
from com.vordel.api.topology.model import Host, Service, Topology, TopologyCertificate
from com.vordel.domain.rbac import AdminUserStoreDAO
from com.vordel.version import ProductVersion
from com.vordel.archive.fed import DeploymentArchive

DOMAIN_KEY_PASSPHRASE = "DOMAIN_KEY_PASSPHRASE"
ANM_PASSPHRASE = "ANM_PASSPHRASE"
ES_PASSPHRASE = "ES_PASSPHRASE"
METRICS_DB_PASSPHRASE = "METRICS_DB_PASSPHRASE"

DISTDIR = vutil.getVDISTDIR()
FEDDIR = os.path.join(DISTDIR, "conf", "fed")


class CertHandler(object):
    """Creates and stores topology cert for Admin Node Manager."""

    LOCAL_NODE_MANAGER_NAME = "Admin Node Manager"
    HOST_ID = "host-1"
    GROUP_ID = "emt_anm_group"
    NODE_MANAGER_ID = "nodemanager-1"

    def __init__(self):
        self.domainCertFile = os.path.join(DISTDIR, "groups", "certs", "domaincert.pem")
        self.domainKeyFile = os.path.join(DISTDIR, "groups", "certs", "private", "domainkey.pem")
        self.debug = False

    def generateCert(self):
        """Generates Admin Node Manager topology cert and key, adds them to FED."""
        print("Generating the Node Manager topology cert:")
        nmHandler = cert.NodeManagerCommHandler(
            CertHandler.NODE_MANAGER_ID, passphrases[ES_PASSPHRASE], passphrases[DOMAIN_KEY_PASSPHRASE], self.debug)

        try:
            self._generateTopologyCert(nmHandler)
            self._storeCertsInEntityStore(nmHandler)

            localNodeManager, topology, topologyParams = self._createTopologyJson()
            print("Enabling SSL on management interface")
            nmHandler.enableSSLInterface(True, TopologyCertificate.CERT_ALIAS, topologyParams)
            self._updateConfigFiles(localNodeManager, topology)

            # Delete the cert generation temp directory
            shutil.rmtree(nmHandler.tempCertPath)

        except Exception, e:
            _fail("Error generating topology cert: %s" % e)

    def _generateTopologyCert(self, nmHandler):
        signAlg = self._getDomainSigningAlgorithm()
        privateKeyFilename = os.path.join(nmHandler.tempCertPath, "adminnodemanagerkey.pem")
        csrFilename = os.path.join(nmHandler.tempCertPath, "adminnodemanager.csr")
        certFilename = os.path.join(nmHandler.tempCertPath, "adminnodemanagercert.pem")
        p12Filename = os.path.join(nmHandler.tempCertPath, "adminnodemanager.p12")
        extensionSection = "admin_node_manager_extensions"
        keyPassphrase = ""

        # Generate topology private key and CSR
        openssl = OpenSSLUtil(nmHandler.tempCertPath, CertHandler.NODE_MANAGER_ID, "", extensionSection, self.debug)
        privateKeyFilename = openssl.generatePrivateKey(privateKeyFilename, keyPassphrase)
        csrFilename = openssl.generateCSR(
            privateKeyFilename, csrFilename,
            "/CN=%s/OU=%s/DC=%s" % (CertHandler.NODE_MANAGER_ID, CertHandler.GROUP_ID, CertHandler.HOST_ID),
            extensionSection, signAlg, keyPassphrase)

        # Sign the cert with the domain private key
        certFilename, signerCertFilename = openssl.signCertificate(
            csrFilename, certFilename, self.domainCertFile, self.domainKeyFile,
            signAlg, passphrases[DOMAIN_KEY_PASSPHRASE])
        p12Filename = openssl.convertPEMToP12(certFilename, privateKeyFilename, p12Filename,
                                              additionalCertFilename=signerCertFilename,
                                              keyPassphrase=keyPassphrase)
        nmHandler.certHandler = CertificateHandler(p12Filename, keyPassphrase)
        certInfo = nmHandler.certHandler.getCertInfo()
        for crt in certInfo.chain:
            if not cert.CertUtil.checkHaveIssuerCert(crt, certInfo.chain):
                _fail("Error: Certificate for '%s' missing from the certificate chain. "
                      "Use a PEM with a full certificate chain." % crt.getIssuerDN().toString())

    def _getDomainSigningAlgorithm(self):
        result = self._runOpenSslCommand("openssl x509 -noout -text -in %s" % self.domainCertFile)
        if "sha384" in result:
            return "sha384"
        if "sha512" in result:
            return "sha512"
        return "sha256"

    def _runOpenSslCommand(self, cmd):
        openSSLExeDir = os.path.abspath(DISTDIR + vutil.getSystemBinDir())
        return _runCommand(cmd, openSSLExeDir)

    def _storeCertsInEntityStore(self, nmHandler):
        print("Storing domain and topology certs in entity store")
        info = nmHandler.certHandler.getCertInfo()
        cert.CertStoreUtil.addCert(nmHandler.getEntityStore(), TopologyCertificate.CERT_ALIAS,
                                   info.certificate, info.privateKey, info.chain)

        nmHandler.debugLog("New %s certificate in federated store:\n\n%s\n"
                           % (cert.branding["node.manager.display.name"], info.certificate.toString()))
        nmHandler.debugLog("Certificate signatures:\n\nSHA1 %s\n\nMD5 %s\n"
                           % (nmHandler.certHandler.getSha1FingerPrint(),
                              nmHandler.certHandler.getMD5FingerPrint()))

    def _createTopologyJson(self):
        print("Creating topology.json file")
        domainId = self._getDomainId()
        topologyParams = UpgradeTopologyParams(domainId, CertHandler.HOST_ID, CertHandler.GROUP_ID, topologyId=None)
        nmCreator = FirstHostManager(HostManager(None, False))
        topology = nmCreator._getTopology(topologyParams)

        host = Host()
        host.setName(CertHandler.HOST_ID)
        nmCreator._setTopologyObjId(topology, host, mdenums.Topology_EntityType_Host, None, False)
        topology.addHost(host)
        group = nmCreator._getGroup(CertHandler.LOCAL_NODE_MANAGER_NAME, None, topology)[0]

        localNodeManager = Service(CertHandler.LOCAL_NODE_MANAGER_NAME, "https", 8090, None, True)
        localNodeManager.setHostID(CertHandler.HOST_ID)
        localNodeManager.setType(mdenums.Topology_ServiceType_nodemanager)
        localNodeManager.getTags().put(Topology.ADMIN_NODE_MANAGER_TAG, "true")
        group.addService(localNodeManager)
        nmCreator._setTopologyObjId(topology, localNodeManager,
                                    mdenums.Topology_EntityType_NodeManager, None, False)
        nmCreator._writeTopology(topology)
        return localNodeManager, topology, topologyParams

    def _getDomainId(self):
        result = self._runOpenSslCommand("openssl x509 -in %s -subject -noout -nameopt multiline"
                                         % self.domainCertFile)
        commonName = re.search(r"commonName *= *(.*)", result, re.MULTILINE).group(1).strip()
        if commonName is None or not re.match("^[A-Za-z]{1}[A-Za-z0-9_-]{0,31}$", commonName):
            _fail("Invalid domain name: '%s'. Permitted characters: [A-Za-z][A-Za-z0-9_-]. "
                  "Must start with a letter, maximum length 32." % commonName)
        return commonName

    def _updateConfigFiles(self, localNodeManager, topology):
        print("Updating nodemanager.xml and envSettings.props files")
        configutil.updateSystemSettings(configutil.getNodeManagerConfFilename(),
                                        configutil.getNodeManagerConfFilename(),
                                        localNodeManager.getId(),
                                        CertHandler.GROUP_ID,
                                        CertHandler.LOCAL_NODE_MANAGER_NAME,
                                        "Node Manager Group",
                                        topology.getId())

        envPropsFile = os.path.join(DISTDIR, "conf", "envSettings.props")
        vutil.updateProperty(envPropsFile, "env.PORT.MANAGEMENT", localNodeManager.managementPort)

#------------------------------------------------------------------------------

def _parseArgs():
    parser = optparse.OptionParser()
    parser.add_option("--props", dest="propsFile",
                      help="Properties file containing name=value pairs.")
    parser.add_option("--fed", dest="fedFile",
                      help="The FED to use for this image.")
    parser.add_option("--anm-username", dest="anmUsername",
                      help="Username for logging into API Gateway Manager UI.")
    parser.add_option("--merge-dir", dest="mergeDir",
                      help="Config directory to merge into apigateway directory.")
    parser.add_option("--healthcheck", dest="healthcheck",
                      help="Indicates whether healthcheck path should be added.")
    parser.add_option("--docker-image-id", dest="dockerImageId",
                      help="Name and version of the Docker image.")
    parser.add_option("--metrics-db-url", dest="metricsDbUrl", default="",
                      help="Metrics database URL. If not provided, metrics is not enabled.")
    parser.add_option("--metrics-db-username", dest="metricsDbUsername",
                      help="Metrics database username.")
    parser.add_option("--fips", dest="fips",
                      help="Indicates whether ANM should start in FIPS mode.")

    opts = parser.parse_args()[0]
    opts.healthcheck = True if opts.healthcheck.lower() in ("1", "true", "yes") else False
    opts.fips = True if opts.fips.lower() in ("1", "true", "yes") else False

    return opts


def _loadPassphrases():
    with open(options.propsFile) as f:
        lines = f.readlines()
    passDict = dict(line.strip().split('=', 1) for line in lines if '=' in line)
    if set(passDict.keys()) != set((DOMAIN_KEY_PASSPHRASE, ANM_PASSPHRASE, ES_PASSPHRASE, METRICS_DB_PASSPHRASE)):
        _fail("Configuration file is missing required properties: %s" % options.propsFile)
    return passDict


def _setup():
    _updateEsPassphrase()
    _extractCustomFedFile()
    _checkLicense()
    _setEnvVariables()
    _setAdminUser()
    _configureMetrics()
    _configureHealthcheck()
    _configureFips()

    if options.mergeDir is not None and os.path.exists(options.mergeDir):
        print("Merging provided config directory into apigateway directory")
        distutils.dir_util.copy_tree(options.mergeDir, DISTDIR)

    ch = CertHandler()
    ch.generateCert()


def _updateEsPassphrase():
    if len(passphrases[ES_PASSPHRASE]) > 0:
        print("Using a custom entity store passphrase")
        diskInstanceMgr = DiskInstanceManager()
        diskInstanceMgr.updateNodeManagerPassphrase(passphrases[ES_PASSPHRASE])


def _extractCustomFedFile():
    if not os.path.exists(options.fedFile):
        print("Using factory FED for Node Manager")
        return

    print("Using custom FED file")
    product, fedVersion = _getProductAndFedVersion()
    productLabel = ProductVersion.getLabel()
    print("   FED Product: %s, FED Version: %s, Product: %s" % (product, fedVersion, productLabel))
    fedPrefix, productPrefix = fedVersion[0:3], productLabel[0:3]

    if "NodeManager" not in product:
        _fail("Provided FED is not a Node Manager FED.")
    if fedPrefix != productPrefix:
        _fail("FED version %s does not match the product version %s" % (fedPrefix, productPrefix))

    print("Deleting factory configuration")
    shutil.rmtree(FEDDIR)
    os.mkdir(FEDDIR)

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
    except Exception, e:
        _fail("Error extracting FED content: %s" % e)


def _getProductAndFedVersion():
    try:
        if os.path.exists(options.fedFile):
            newArchive = DeploymentArchive(options.fedFile)
            es = EntityStoreAPI.wrap(newArchive.getEntityStore(), passphrases[ES_PASSPHRASE])
        else:
            es = EntityStoreAPI.create("file:///%s/conf/fed/PrimaryStore.xml" % DISTDIR,
                                       passphrases[ES_PASSPHRASE], {"strictImportSchema": "false"})
        productKey = es.getProductKey()
        fedVersion = es.getVersion()
        es.close()
        return productKey, fedVersion
    except (Exception, Throwable), e:
        _fail("Error reading the FED: %s" % e)


def _checkLicense():
    licenseFile = os.path.join(DISTDIR, "conf", "licenses", "lic.lic")
    if not os.path.exists(licenseFile):
        if options.fips:
            _fail("FIPS mode specified but no license file supplied.")
        print("No license file supplied")
        return

    print("Checking license")
    with open(licenseFile) as f:
        s = f.read()

    if options.fips and not re.search("FIPS *= *1", s):
        _fail("Supplied license file is not valid for FIPS mode.")

    matcher = re.search(r"expires *=.*, ([\d]{2}) ([A-Za-z]{3}) ([\d]{4})", s)
    if matcher is not None:
        day, monthStr, year = matcher.group(1), matcher.group(2), matcher.group(3)
        month = list(calendar.month_abbr).index(monthStr)
        expiryDate = datetime.date(int(year), int(month), int(day))
        if expiryDate < datetime.date.today():
            _fail("Supplied license file has expired.")


def _setEnvVariables():
    venvPath = os.path.join(DISTDIR, "posix", "lib", "venv")
    print("Setting env variables:")
    with open(venvPath, 'a') as f:
        print("   EMT_ENABLED=true")
        f.write("\nexport EMT_ENABLED=true")
        print("   EMT_IMAGE_ID=%s" % options.dockerImageId)
        f.write("\nexport EMT_IMAGE_ID=%s" % options.dockerImageId)
        if options.fips:
            print("   EMT_FIPS_MODE=true")
            f.write("\nexport EMT_FIPS_MODE=true")


def _setAdminUser():
    if len(passphrases[ANM_PASSPHRASE]) > 0:
        print("Creating custom admin user")
        store = AdminUserStoreDAO()
        store.createInitialAdminUserStore(options.anmUsername, String(passphrases[ANM_PASSPHRASE]).toCharArray())
        store.write(os.path.join(DISTDIR, "conf"))


def _configureMetrics():
    if len(options.metricsDbUrl) > 0:
        print("Configuring Admin Node Manager to write to metrics database")
        params = MetricsParams(isConfigureMetrics=True, isMetricsEnabled=True, dbURL=options.metricsDbUrl,
                               dbUserName=options.metricsDbUsername,
                               dbPlaintextPassword=passphrases[METRICS_DB_PASSPHRASE],
                               entityStorePassword=passphrases[ES_PASSPHRASE])
        manager = MetricsManager()
        if not manager.updateMetricsSettingsInEntityStore(params):
            _fail("Failed to update metrics configuration settings.")


def _configureHealthcheck():
    if not options.healthcheck:
        return

    es = None
    try:
        pattern = re.compile("ListenersStore.*xml")
        listenersStore = [fname for fname in os.listdir(FEDDIR) if re.match(pattern, fname)][0]
        es = EntityStoreAPI.create("file:///%s/conf/fed/%s" % (DISTDIR, listenersStore),
                                   passphrases[ES_PASSPHRASE], {"strictImportSchema": "false"})
        print("Adding /healthcheck path to management port")
        es.importConf(os.path.join(DISTDIR, "samples", "SamplePolicies", "HealthCheck", "anm_hc_path.xml"))

    except (Exception, Throwable), e:
        _fail("Error adding /healthcheck path: %s" % e)
    finally:
        if es is not None:
            es.close()


def _configureFips():
    if options.fips:
        print("Enabling FIPS mode")
        fc = FipsController()
        fc.enableFipsSwitch()
        _runCommand("%s on" % os.path.join(DISTDIR, "posix", "bin", "fips"))


def _runCommand(cmd, runDir=None):
    if runDir is not None:
        currWorkingDir = os.getcwd()
        os.chdir(runDir)
    cmd = shlex.split(cmd)
    bosErr = ByteArrayOutputStream()
    origStdErr = System.err
    System.setErr(PrintStream(bosErr))
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    System.setErr(origStdErr)
    if runDir is not None:
        os.chdir(currWorkingDir)
    if process.wait() != 0:
        errorStr = "Failed to call '%s'. Error: %s" % (cmd, String(bosErr.toByteArray()))
        _fail(errorStr)
    return process.communicate()[0]


def _fail(msg, errorCode=1):
    """Prints an error message in red."""
    print("""\033[91m
=====================================ERROR=====================================
%s
===============================================================================\n\033[0m""" % msg)
    sys.exit(errorCode)


if __name__ == "__main__":
    print("\nSetting up Node Manager...\n")
    options = _parseArgs()
    passphrases = _loadPassphrases()
    _setup()
    print("\nNode Manager setup complete.\n")
