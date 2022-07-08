"""Configures a Docker container to run an API Gateway."""
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
import tarfile

import cert
import vutil

from apimgmtconfig import ApiManagerConfig
from diskinstancemanager import DiskInstanceManager
from esapi import ArchiveInfo, EntityStoreAPI
from openssl import OpenSSLUtil

from java.io import ByteArrayOutputStream, PrintStream
from java.lang import String, System, Throwable

from com.vordel.api.connection import CertificateHandler
from com.vordel.api.domain.controller import FipsController
from com.vordel.api.topology.model import TopologyCertificate
from com.vordel.archive.fed import DeploymentArchive, EnvironmentArchive, PolicyArchive
from com.vordel.es.xes import PortableESPK
from com.axway.gw.es.yaml import YamlEntityStore
from com.vordel.version import ProductVersion
from com.vordel.es.store.util import Versioner

DOMAIN_KEY_PASSPHRASE = "DOMAIN_KEY_PASSPHRASE"
ES_PASSPHRASE = "ES_PASSPHRASE"

os.environ["EMT_ENABLED"] = "true"

DISTDIR = vutil.getVDISTDIR()
GROUP_NAME = "emt-group"
SERVICE_NAME = "emt-service"
HOST_ID = "host-1"
INSTDIR = os.path.join(DISTDIR, "groups", "topologylinks", "%s-%s" % (GROUP_NAME, SERVICE_NAME))

DOMAIN_CERT_FILE = os.path.join(DISTDIR, "groups", "certs", "domaincert.pem")
DOMAIN_KEY_FILE = os.path.join(DISTDIR, "groups", "certs", "private", "domainkey.pem")
FACTORY_FED_FILENAME = ("FactoryConfiguration-%s.fed" % vutil.getBrandingMap()["server.instanceServiceType"])
FACTORY_FED_FILE = os.path.join(DISTDIR, "system", "conf", "templates", FACTORY_FED_FILENAME)
FACTORY_YAML_FILENAME = ("FactoryConfiguration-%s.tar.gz" % vutil.getBrandingMap()["server.instanceServiceType"])
FACTORY_YAML_CONFIG = os.path.join(DISTDIR, "system", "conf", "templates", "yaml", FACTORY_YAML_FILENAME)

class CertHandler(object):
    """Creates and stores topology cert for API Gateway."""

    def __init__(self):
        self.subjectAltNames = ""
        self.signAlg = self._getDomainSigningAlgorithm()
        self.debug = False
        self.gwHandler = cert.GatewayCommHandler(SERVICE_NAME, GROUP_NAME, self.debug, True)

    def _getDomainSigningAlgorithm(self):
        """Returns the signing algorithm used by the domain cert.
        The same algorithm is used for the topology cert."""
        result = _runOpenSslCommand("openssl x509 -noout -text -in %s" % DOMAIN_CERT_FILE)
        if "sha384" in result:
            return "sha384"
        if "sha512" in result:
            return "sha512"
        return "sha256"

    def generateCert(self):
        """Generates API Gateway topology cert and key."""
        print("Generating API Gateway topology cert:")
        try:
            print("   Generating topology CSR and private key")
            self._updateOpensslConf()
            privateKeyFilename, csrFilename = self.gwHandler.makeNewCSR(
                GROUP_NAME, HOST_ID, self.subjectAltNames, self.signAlg, keyPassphrase="")

            tmpCertPath = vutil.ensurePath(os.path.join(self.gwHandler.privateCertPath, "temp", SERVICE_NAME))
            (certChain, certFilename) = self._signCSR(tmpCertPath, csrFilename)
            self._convertPEMToP12(certFilename, privateKeyFilename)
            self._createCertXml(certChain, privateKeyFilename)

            shutil.rmtree(tmpCertPath)

        except Exception, e:
            _fail("Error generating topology cert: %s" % e)

    def _updateOpensslConf(self):
        opensslCnfTemplate = os.path.join(DISTDIR, "skel", "openssl.cnf")
        with open(opensslCnfTemplate) as f:
            s = f.read()
            if r"extendedKeyUsage = serverAuth, 1.3.6.1.4.1.17998.10.1.1.2.3" in s:
                s = re.sub(r"extendedKeyUsage = serverAuth, 1.3.6.1.4.1.17998.10.1.1.2.3",
                           "extendedKeyUsage = serverAuth, clientAuth, 1.3.6.1.4.1.17998.10.1.1.2.3", s)
            else:
                _fail("Error updating %s. Failed to find Gateway extensions extendedKeyUsage" % opensslCnfTemplate)
        with open(opensslCnfTemplate, 'w') as f:
            f.write(s)

    def _signCSR(self, tmpCertPath, csrFilename):
        print("   Signing topology cert with domain private key")
        certFilename = os.path.join(tmpCertPath, "instancecert.pem")
        openssl = OpenSSLUtil(tmpCertPath, SERVICE_NAME, [], "gateway_extensions", self.debug)
        certFilename, signerCertFilename = openssl.signCertificate(
            csrFilename, certFilename, DOMAIN_CERT_FILE, DOMAIN_KEY_FILE, self.signAlg,
            passphrases[DOMAIN_KEY_PASSPHRASE])

        # Cert chain includes topology cert, domain cert, and all certs in domain cert's chain
        with open(certFilename) as f:
            topologyCert = f.read()
        certChain = [topologyCert]
        signerChain = cert.CertUtil.extractCertChain(signerCertFilename)

        certChain += signerChain
        return (certChain, certFilename)

    def _convertPEMToP12(self, certFilename, privateKeyFilename):
        print("   Converting topology cert and private key to pP12")
        p12Filename = os.path.join(DISTDIR, "groups", "certs", "topology.p12")
        params = {"cert":certFilename, "privateKeyFile":privateKeyFilename, "p12":p12Filename,
                  "passphrase":passphrases[ES_PASSPHRASE]}
        cmd = ('openssl pkcs12 -keypbe PBE-SHA1-3DES -certpbe PBE-SHA1-3DES -export -in "%(cert)s" '
               '-inkey "%(privateKeyFile)s" -out "%(p12)s" ' % params)
        if passphrases[ES_PASSPHRASE] != "":
            cmd += ' -passin pass:"%(passphrase)s" -passout pass:"%(passphrase)s"' % params
        else:
            cmd += ' -passout pass:'
        _runOpenSslCommand(cmd)


    def _createCertXml(self, certChain, privateKeyFilename):
        print("   Storing domain and topology certs in certs.xml file")
        gatewayCertInfo = cert.CertUtil.createPersonalInfo(certChain, privateKeyFilename, passphrases[ES_PASSPHRASE])
        self.gwHandler.certHandler = CertificateHandler(gatewayCertInfo)
        if self.gwHandler.certHandler is None:
            _fail("Failed to create certs.xml file")

        certInfo = self.gwHandler.certHandler.getCertInfo()
        for crt in certInfo.chain:
            if not cert.CertUtil.checkHaveIssuerCert(crt, certInfo.chain):
                _fail("Error: Certificate for '%s' missing from the certificate chain. "
                      "Use a PEM with a full certificate chain." % crt.getIssuerDN().toString())
        xmlStore = cert.CertXMLUtil.makeXMLStore(certInfo, TopologyCertificate.CERT_ALIAS, passphrases[ES_PASSPHRASE])
        xmlStore.write(os.path.join(INSTDIR, "conf", "certs.xml"))

    def enableSSLInterface(self):
        """Updates management interface to use topology cert."""
        try:
            print("   Updating management interface to use topology cert for SSL")
            self.gwHandler.enableSSLInterface(TopologyCertificate.CERT_ALIAS)

            print("   Updating mgmt.xml to load topology cert")
            mgmtXml = os.path.join(INSTDIR, "conf", "mgmt.xml")
            with open(mgmtXml) as f:
                s = f.read()
            s = re.sub("localhost", "*", s)
            s = re.sub("<VerifyIsLocalNodeManager */> *\n", "", s)
            with open(mgmtXml, 'w') as f:
                f.write(s)
        except Exception, e:
            _fail("Error enabling SSL interface: %s" % e)

#------------------------------------------------------------------------------

def _parseArgs():
    parser = optparse.OptionParser()
    parser.add_option("--props", dest="propsFile",
                      help="Properties file containing name=value pairs.")
    parser.add_option("--group-id", dest="groupId",
                      help="The ID/name of the API Gateway group.")
    parser.add_option("--factory-yaml", dest="factoryYaml",
                      help="Indicates whether the factory YAML configuration should be used")
    parser.add_option("--fed", dest="fedFile",
                      help="The FED to use for this image.")
    parser.add_option("--pol", dest="polFile",
                      help="The POL to use for this image.")
    parser.add_option("--env", dest="envFile",
                      help="The ENV to use for this image.")
    parser.add_option("--yaml", dest="yamlConfig",
                      help="The YAML configuration to use for this image.")
    parser.add_option("--merge-dir", dest="mergeDir",
                      help="Config directory to merge into apigateway directory.")
    parser.add_option("--docker-image-id", dest="dockerImageId",
                      help="Name and version of the Docker image.")
    parser.add_option("--setup-apimgr", dest="setupApimgr",
                      help="Indicates whether API Manager should be configured.")
    parser.add_option("--fips", dest="fips",
                      help="Indicates whether Gateway should start in FIPS mode.")

    opts = parser.parse_args()[0]
    opts.setupApimgr = (opts.setupApimgr.lower() in ("1", "true", "yes"))
    opts.factoryYaml = (opts.factoryYaml.lower() in ("1", "true", "yes"))
    opts.fips = (opts.fips.lower() in ("1", "true", "yes"))

    return opts


def _loadPassphrases():
    with open(options.propsFile) as f:
        lines = f.readlines()
    passDict = dict(line.strip().split('=', 1) for line in lines if '=' in line)
    if set(passDict.keys()) != set((DOMAIN_KEY_PASSPHRASE, ES_PASSPHRASE)):
        _fail("Configuration file is missing required properties: %s" % options.propsFile)
    return passDict


def _setup():
    _mergePolAndEnvToFed()
    
    # Specify which configuration type is being used: factory fed, factory yaml, custom fed or custom yaml
    # Defaults to factory FED.
    if os.path.exists(options.yamlConfig):
        _installCustomYamlConfig()
    elif os.path.exists(options.fedFile):
        _installCustomFedFile()
    elif options.factoryYaml:
        print ("Using factory yaml configuration for API Gateway")
    else:
        print ("Using factory FED file for API Gateway")

    # Only used with factory FED; cannot be specified with any other configuration
    if options.setupApimgr:
        _setupApiManager()
    
    _createInstanceDirStructure()
    _customizeInstallation()
    _checkLicense()

    ch = CertHandler()
    ch.generateCert()
    ch.enableSSLInterface()


def _mergePolAndEnvToFed():
    if os.path.exists(options.polFile) and os.path.exists(options.envFile):
        print("Merging POL and ENV to make a FED")
        stagingPol = PolicyArchive(options.polFile)
        stagingEnv = EnvironmentArchive(options.envFile)
        mergedArchive = DeploymentArchive(stagingPol, stagingEnv, passphrases[ES_PASSPHRASE])

        outFile = os.path.join(os.path.dirname(options.polFile), "fed.fed")
        mergedArchive.writeToArchiveFile(outFile)
        options.fedFile = outFile


def _installCustomYamlConfig():
        print("Using custom YAML config for API Gateway")
        product, yamlVersion = _getProductAndYamlVersion()
        productLabel = ProductVersion.getLabel()
        print("YAML Product: %s, YAML Version: %s, Product: %s" % (product, yamlVersion, productLabel))
        yamlPrefix, productPrefix = yamlVersion[0:3], productLabel[0:3]
        if "Gateway" not in product:
            _fail("Provided YAML Config is not an API Gateway YAML configuration.")
        if yamlPrefix != productPrefix:
            _fail("YAML version %s does not match the product version %s" % (yamlPrefix, productPrefix))

        print ("Replacing factory YAML template with provided YAML config")
        with tarfile.open(FACTORY_YAML_CONFIG, "w:gz") as tar:
            for fn in os.listdir(options.yamlConfig):
                p = os.path.join(options.yamlConfig, fn)
                tar.add(p, arcname=fn)


def _installCustomFedFile():
    print("Using custom FED file for API Gateway")
    product, fedVersion = _getProductAndFedVersion()
    productLabel = ProductVersion.getLabel()
    print("FED Product: %s, FED Version: %s, Product: %s" % (product, fedVersion, productLabel))
    fedPrefix, productPrefix = fedVersion[0:3], productLabel[0:3]

    if "Gateway" not in product:
        _fail("Provided FED is not an API Gateway FED.")
    if fedPrefix != productPrefix:
        _fail("FED version %s does not match the product version %s" % (fedPrefix, productPrefix))

    print ("Replacing factory FED template with provided FED file")
    shutil.copy(options.fedFile, FACTORY_FED_FILE)


def _getProductAndFedVersion():
    try:
        newArchive = DeploymentArchive(options.fedFile)
        es = EntityStoreAPI.wrap(newArchive.getEntityStore(), passphrases[ES_PASSPHRASE])
        productKey = es.getProductKey()
        fedVersion = es.getVersion()
        es.close()
        return productKey, fedVersion
    except (Exception, Throwable), e:
        _fail("Error reading the FED: %s" % e)


def _getProductAndYamlVersion():
    try:
        yamlES = YamlEntityStore()
        yamlES.connect("yaml:file:" + options.yamlConfig, None)
        productKey = Versioner.getProductKey(yamlES)
        yamlVersion = Versioner.getVersion(yamlES)
        return productKey, yamlVersion
    except (Exception, Throwable), e:
        _fail("Error reading the YAML Config: %s" % e)


def _createInstanceDirStructure():
    if len(passphrases[ES_PASSPHRASE]) > 0:
        print("Using a custom entity store passphrase")

    diskInstanceMgr = DiskInstanceManager()
    diskInstanceMgr.setGroupName(GROUP_NAME)
    diskInstanceMgr.setPassphrase(passphrases[ES_PASSPHRASE])
    diskInstanceMgr.setServiceName(SERVICE_NAME)
    diskInstanceMgr.setServiceID(SERVICE_NAME)
    diskInstanceMgr.setGroupID(GROUP_NAME)
    diskInstanceMgr.setDomainID(_getDomainId())
    diskInstanceMgr.setServicesPort("8080")
    diskInstanceMgr.setManagementPort("8085")
    if os.path.exists(options.yamlConfig) or options.factoryYaml:
        diskInstanceMgr.setInitFirstGatewayWithYaml(True)
    diskInstanceMgr.setDeploymentArchives([])
    diskInstanceMgr.createInstance()
    diskInstanceMgr.updateGroupPassphrase("", passphrases[ES_PASSPHRASE])


def _getDomainId():
    result = _runOpenSslCommand("openssl x509 -in %s -subject -noout -nameopt multiline" % DOMAIN_CERT_FILE)
    commonName = re.search(r"commonName *= *(.*)", result, re.MULTILINE).group(1).strip()
    if commonName is None or not re.match("^[A-Za-z]{1}[A-Za-z0-9_-]{0,31}$", commonName):
        _fail("Invalid domain name: '%s'. Permitted characters: [A-Za-z][A-Za-z0-9_-]. "
              "Must start with a letter, maximum length 32." % commonName)
    return commonName


def _runOpenSslCommand(cmd):
    openSSLExeDir = os.path.abspath(DISTDIR + vutil.getSystemBinDir())
    return _runCommand(cmd, openSSLExeDir)


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


def _customizeInstallation():
    print("Setting group name & ID")
    serviceidsPath = os.path.join(INSTDIR, "conf", "serviceids.xml")
    with open(serviceidsPath) as f:
        s = f.read()
    s = s.replace("emt-group", options.groupId)
    with open(serviceidsPath, 'w') as f:
        f.write(s)

    print("Enabling HTTP 1.1")
    servicePath = os.path.join(INSTDIR, "conf", "service.xml")
    with open(servicePath) as f:
        s = f.read()
    s = s.replace("<SystemSettings ", '<SystemSettings allowHTTP11="true" maxThreads="1024" ')
    with open(servicePath, 'w') as f:
        f.write(s)

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

    if options.fips:
        print("Enabling FIPS mode")
        fc = FipsController()
        fc.enableFipsSwitch()
        _runCommand("%s on" % os.path.join(DISTDIR, "posix", "bin", "fips"))

    if options.mergeDir is not None and os.path.exists(options.mergeDir):
        print("Merging provided config directory into apigateway directory")
        distutils.dir_util.copy_tree(options.mergeDir, DISTDIR)

    opsdbDir = os.path.join(INSTDIR, "conf/opsdb.d")
    try:
        os.mkdir(opsdbDir)
    except OSError, e:
        print("Error creating directory '%s': %s" % (opsdbDir, e))


def _setupApiManager():
    try:
        # Add API Manager configuration to factory FED
       archive = DeploymentArchive(FACTORY_FED_FILE)
       config = ApiManagerConfig()
       config.adminPassword = "changeme"
       archiveInfo = ArchiveInfo(archive, passphrases[ES_PASSPHRASE], EntityStoreAPI.wrap(archive.getEntityStore(), passphrases[ES_PASSPHRASE]))
       es, archive = config.loadAPIManagerConfigurationToArchive(archiveInfo)

       # Default Cassandra host is '${environment.CASS_HOST}'. This can be overridden
       # by comma-separated list of hosts in env variable APIMGR_CASS_HOSTS.
       cassHosts = os.environ.get("APIMGR_CASS_HOSTS", "${environment.CASS_HOST}").strip()
       if len(cassHosts) == 0:
           cassHosts = "${environment.CASS_HOST}"
       for i, s in enumerate(cassHosts.split(",")):
           cassHost = s.strip()
           print("   Adding Cassandra host with hostname '%s'" % cassHost)
           props = {"name": "casshost%s" % (i + 1),
                    "host": "%s" % cassHost,
                    "port": "9042"}
           parent = es.get("/[CassandraSettings]name=Cassandra Settings")
           es.addNewEntity(parent, "CassandraServer", props)

       # Enable API Manager metrics. Connection to metrics DB will be configured via
   # environment variables.
       print("   Enabling API Manager metrics")
       db = es.get("/[DbConnectionGroup]name=Database Connections/[DbConnection]name=Default Database Connection")
       db.setStringField("url", "${environment.METRICS_DB_URL}")
       db.setStringField("username", "${environment.METRICS_DB_USERNAME}")
       db.setStringField("passwordType", "wildcard")
       db.setStringField("wildcardPassword", "${environment.METRICS_DB_PASS}")
       es.updateEntity(db)

       portalConfig = es.get("/[PortalConfiguration]name=Portal Config")
       portalConfig.setBooleanField("metricsStoringEnabled", True)
       portalConfig.setReferenceField("dbConn", PortableESPK.toPortableKey(es.es, db.getPK()))
       es.updateEntity(portalConfig)

       archive.updateConfiguration(es.es)
       es.close()
       archive.writeToArchiveFile(FACTORY_FED_FILE)

    except (Exception, Throwable), e:
        _fail("Error configuring API Manager: %s" % e)


def _checkLicense():
    apiManagerUsed = _checkFeaturesUsed()
    print("Checking license")
    with open(os.path.join(DISTDIR, "conf", "licenses", "lic.lic")) as f:
        s = f.read()

    if not re.search("unrestricted *= *1", s):
        _fail("Supplied license file is not valid for API Gateway.")
    if apiManagerUsed and not re.search("apiportal *= *1", s):
        _fail("Supplied license file is not valid for API Manager, but API Manager is configured in the FED.")
    if options.fips and not re.search("FIPS *= *1", s):
        _fail("Supplied license file is not valid for FIPS mode.")

    matcher = re.search(r"expires *=.*, ([\d]{2}) ([A-Za-z]{3}) ([\d]{4})", s)
    if matcher is not None:
        day, monthStr, year = matcher.group(1), matcher.group(2), matcher.group(3)
        month = list(calendar.month_abbr).index(monthStr)
        expiryDate = datetime.date(int(year), int(month), int(day))
        if expiryDate < datetime.date.today():
            _fail("Supplied license file has expired.")


def _checkFeaturesUsed():
    print("Checking which Gateway features are used:")
    apiManagerUsed = False

    # Find gateway FED/yaml config directory
    esidFile = os.path.join(INSTDIR, "conf", "esid.xml")
    with open(esidFile) as f:
        s = f.read()
    pattern = re.compile('property *= *"esid" *value *= *"(.*)"')
    esid = re.search(pattern, s).group(1).strip()
    configDir = os.path.join(DISTDIR, "groups", GROUP_NAME, "conf", esid)
    if os.path.exists(options.yamlConfig) or options.factoryYaml is not None:
        apiManagerConfig = configDir+"/Server Settings/Portal Config.yaml"
        if os.path.exists(apiManagerConfig):
            apiManagerUsed = True
            with open(apiManagerConfig) as f:
                s = f.read()
            pattern = re.compile('adminPassword: $')
            if re.search(pattern, s):
                _fail("API Manager is configured but the API administrator has no default password.\n"
                      "Open the YAML configuration in Policy Studio and fill in the Default Administrator Password "
                      "at Server Settings > API Manager.")
            
    else:
        # Check PrimaryStore.xml to see if API Manager are used
        pattern = re.compile("PrimaryStore.*xml")
        primaryStore = [fname for fname in os.listdir(configDir) if re.match(pattern, fname)][0]
        with open(os.path.join(configDir, primaryStore)) as f:
            s = f.read()

        pattern = re.compile('<entity .* type="PortalConfiguration"')
        if re.search(pattern, s):
            apiManagerUsed = True
            pattern = re.compile('name="adminPassword"><value>.+</value')
            if not re.search(pattern, s):
                _fail("API Manager is configured but the API administrator has no default password.\n"
                      "Open the FED in Policy Studio and fill in the Default Administrator Password "
                      "at Server Settings > API Manager.")
    print("   API Manager: %s" % apiManagerUsed)

    return apiManagerUsed


def _fail(msg, errorCode=1):
    """Prints an error message in red."""
    print("""\033[91m
=====================================ERROR=====================================
%s
===============================================================================\n\033[0m""" % msg.encode("utf-8"))
    sys.exit(errorCode)


if __name__ == "__main__":
    print("\nSetting up API Gateway...\n")
    options = _parseArgs()
    passphrases = _loadPassphrases()
    _setup()
    print("\nAPI Gateway setup complete.\n")
