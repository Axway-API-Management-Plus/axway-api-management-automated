"""Utility for untarring a file into a specified directory."""
import sys
import tarfile


def untar(inFile, outDir):
    """Untars inFile into outDir."""
    try:
        with tarfile.open(inFile, 'r') as f:
            f.extractall(outDir)
    except Exception as e:
        sys.exit("Error extracting tar file: %s" % e)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("Usage: %s TAR_FILE OUTPUT_DIR" % sys.argv[0])
    untar(sys.argv[1], sys.argv[2])
