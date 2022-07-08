#!/usr/bin/env python3
"""Generates a self-signed CA cert or a CSR for an API Gateway domain."""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time

from utils.utils import VERSION, fail, runOpenSslCmd


def _parseArgs():
    parser = argparse.ArgumentParser(
        description="Generates a self-signed CA cert or a CSR for an API Gateway domain.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Examples\n"
                "--------\n"
                "# Generate default domain cert and key\n"
                "./gen_domain_cert.py --default-cert\n\n"
                "# Generate cert with domainId=mydomain, passphrase in /tmp/pass.txt\n"
                "./gen_domain_cert.py --domain-id=mydomain --pass-file=/tmp/pass.txt\n\n"
                "# Generate CSR with domainId=mydomain, passphrase in /tmp/pass.txt, O=MyOrg\n"
                "./gen_domain_cert.py --domain-id=mydomain --pass-file=/tmp/pass.txt --out=csr --O=MyOrg"))

    parser._action_groups.pop()
    grp1 = parser.add_argument_group("arguments")
    grp1.add_argument("--version", action="version", version=VERSION,
                      help="Show version information and exit.")
    grp1.add_argument("--domain-id", dest="domainId",
                      help="Unique ID for API Gateway domain. Used as the common name (CN) in the domain "
                      "CA cert. Permitted characters: [A-Za-z0-9_-]. Must start with a letter, max length 32.")
    grp1.add_argument("--pass-file", dest="passFile",
                      help="File containing passphrase for the domain private key.")
    grp1.add_argument("--out", dest="out", choices=["self-signed-cert", "csr"], default="self-signed-cert",
                      help="Output type (default: self-signed-cert).")
    grp1.add_argument("--force", dest="force", action='store_true', default=False,
                      help="Overwrite existing cert/CSR for this domain-id.")
    grp1.add_argument("--sign-alg", dest="signAlg", choices=["SHA256", "SHA384", "SHA512"], default="SHA256",
                      help="Signing algorithm for self-signed domain cert (default: SHA256).")
    grp1.add_argument("--O", dest="org",
                      help="Value for O (organization) field in the domain cert, e.g., Sales Org.")
    grp1.add_argument("--OU", dest="orgUnit",
                      help="Value for OU (organizational unit) field in the domain cert, e.g., Staging.")
    grp1.add_argument("--C", dest="country",
                      help="Value for C (country) field in the domain cert, e.g., US.")
    grp1.add_argument("--ST", dest="state",
                      help="Value for the ST (state/county/region) field in the domain cert, e.g., New York.")
    grp1.add_argument("--L", dest="locality",
                      help="Value for the L (locality/city) field in the domain cert, e.g., Rochester.")

    grp2 = parser.add_argument_group("arguments for NON-PRODUCTION environment")
    grp2.add_argument("--default-cert", dest="defaultCert", action="store_true", default=False,
                      help="Generate default cert and key. Equivalent to specifying "
                      "domain-id=DefaultDomain, passphrase=changeme.")

    # Print help if script called without arguments
    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    return parser.parse_args()


def _validateArgs():
    if args.defaultCert:
        if (args.domainId, args.passFile, args.out) != (None, None, "self-signed-cert"):
            fail("If you specify --default-cert, cannot also specify --domain-id, --pass-file or --out=csr.")
        args.domainId = "DefaultDomain"
    else:
        if None in (args.domainId, args.passFile):
            fail("Must specify --default-cert or both --domain-id and --pass-file.")
        if not re.match("^[A-Za-z]{1}[A-Za-z0-9_-]{0,31}$", args.domainId):
            fail("Invalid domain name: '%s'. Permitted characters: [A-Za-z0-9_-]. "
                 "Must start with a letter, max length 32." % args.domainId)
        if not os.path.exists(args.passFile):
            fail("Password file does not exist: %s" % args.passFile)
        minPassphraseLength = 4
        with open(args.passFile, 'r') as f:
            content = f.read()
            contentNoLFCR = content.rstrip('\r\n')
            if (len(contentNoLFCR) < minPassphraseLength):
                fail("Passphase provided is too short. Length is %d, expected >= %d." % \
                    (len(contentNoLFCR), minPassphraseLength))


def _setup():
    # Create directory to hold generated key and csr/cert
    generatedCertsDir = os.path.join(os.path.dirname(__file__), "certs", args.domainId)
    if os.path.exists(generatedCertsDir):
        if args.force:
            print("Removing existing output directory: %s" % generatedCertsDir)
            shutil.rmtree(generatedCertsDir)
        else:
            fail("Output directory already exists for this domain-id: %s\nUse --force to overwrite." % generatedCertsDir)
    os.makedirs(generatedCertsDir)

    # Create temporary passphrase file if default cert being generated
    if args.defaultCert:
        args.passFile = os.path.join(generatedCertsDir, "default-pass-file.txt")
        with open(args.passFile, 'w') as f:
            f.write("changeme")

    # Instantiate openssl conf file from template
    openSslTemplate = os.path.join(os.path.dirname(__file__), "utils", "openssl-template.cnf")
    opensslCnfFile = os.path.join(generatedCertsDir, "openssl.cnf")
    shutil.copyfile(openSslTemplate, opensslCnfFile)
    with open(opensslCnfFile) as f:
        s = f.read()
        s = re.sub(r"basedir = \?", "basedir = %s" % generatedCertsDir, s)
        s = re.sub("domaincert.pem", "%s-cert.pem" % args.domainId, s)
        s = re.sub("domainkey", "%s-key" % args.domainId, s)
    with open(opensslCnfFile, 'w') as f:
        f.write(s)
    os.environ["OPENSSL_CONF"] = opensslCnfFile

    # Create openssl helper files
    with open(os.path.join(generatedCertsDir, "index.txt"), 'w') as _:
        pass
    with open(os.path.join(generatedCertsDir, "serial"), 'w') as serialFile:
        firstserial = hex(int(round(time.time() * 1000)))[2:]
        if len(firstserial) % 2 != 0:
            firstserial = "0%s" % firstserial
        serialFile.write(firstserial)

    return (opensslCnfFile, generatedCertsDir)


def _createDomainCert():
    privateKeyFile = _generatePrivateKey()

    csrFile = _generateCSR(privateKeyFile)

    if args.out == "csr":
        print("Done.\n\nPrivate key: %s\nCSR: %s\n\nThis CSR must be signed by an "
              "external CA to produce a domain cert." % (privateKeyFile, csrFile))
    else:
        certFile = _generateCert(csrFile)
        print("Done.\n\nPrivate key: %s\nDomain cert: %s" % (privateKeyFile, certFile))


def _generatePrivateKey():
    pemFilename = os.path.join(generatedCertsPath, "%s-key.pem" % args.domainId)
    try:
        print("Generating private key...")
        opensslCmd = "openssl genrsa -out %s -des -passout file:%s 2048" % (pemFilename, args.passFile)
        runOpenSslCmd(opensslCmd)
    except IOError as e:
        fail("Failed to generate Private Key: %s" % os.strerror(e.errno))
    return pemFilename


def _generateCSR(privateKeyFile):
    print("Generating CSR...")
    domainInfo = _getDomainInfo()
    csrFile = os.path.join(generatedCertsPath, "%s.csr" % args.domainId)
    params = {"signAlg":args.signAlg, "privateKeyFile":privateKeyFile, "csrFile":csrFile,
              "domainInfo":domainInfo, "opensslCnf": opensslCnf, "passFile":args.passFile}
    opensslCmd = ('openssl req -%(signAlg)s -new -key "%(privateKeyFile)s" -out "%(csrFile)s" -subj "%(domainInfo)s" '
                  '-reqexts domain_extensions -config "%(opensslCnf)s" -passin file:"%(passFile)s"' % params)
    try:
        runOpenSslCmd(opensslCmd)
    except IOError as e:
        fail("Failed to generate CSR: %s" % os.strerror(e.errno))
    return csrFile


def _getDomainInfo():
    certFields = {"O":args.org, "OU":args.orgUnit, "C":args.country, "ST":args.state, "L":args.locality}
    domainInfo = "/CN=%s" % args.domainId
    for key, value in certFields.items():
        if value:
            domainInfo += "/%s=%s" % (key, value)
    return domainInfo


def _generateCert(csrFile):
    print("Generating self-signed domain cert...")
    certFile = os.path.join(generatedCertsPath, "%s-cert.pem" % args.domainId)
    startDate = _getStartDate()
    params = {"startDate":startDate, "signAlg":args.signAlg, "csrFile":csrFile,
              "certFile":certFile, "opensslCnf":opensslCnf, "passFile":args.passFile}
    # Specify -extfile to get a v3 certificate. Need a v3 certificate for SSL to work.
    # Do not specify -extensions section as we want to copy extensions from the CSR via
    # "copy_extensions = copyall" in openssl.cnf.
    opensslCmd = ('openssl ca -startdate %(startDate)s -md %(signAlg)s -in "%(csrFile)s" -out "%(certFile)s" '
                  '-extfile "%(opensslCnf)s" -batch -notext -passin file:"%(passFile)s" -selfsign' % params)
    try:
        runOpenSslCmd(opensslCmd)
    except IOError as e:
        fail("Failed to generate certificate: %s" % os.strerror(e.errno))
    return certFile


def _getStartDate():
    datetimeFormat = "%y%m%d%H%M%SZ"
    now = datetime.datetime.utcnow()
    start = now + datetime.timedelta(days=-7)
    return start.strftime(datetimeFormat)


def _cleanup():
    for fname in os.listdir(generatedCertsPath):
        fpath = os.path.join(generatedCertsPath, fname)
        try:
            if args.out == "self-signed-cert":
                if "-cert.pem" not in fname and "-key.pem" not in fname:
                    os.unlink(fpath)
            else:
                if ".csr" not in fname and "-key.pem" not in fname:
                    os.unlink(fpath)
        except Exception as e:
            print("Error cleaning up: %s" % e)


if __name__ == "__main__":
    args = _parseArgs()
    _validateArgs()
    # Verify that openssl is installed
    runOpenSslCmd("openssl version")

    opensslCnf, generatedCertsPath = _setup()
    _createDomainCert()
    _cleanup()
