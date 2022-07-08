"""Utility for unzipping a file into a specified directory."""
import sys
import zipfile


def unzip(inFile, outDir):
    """Unzips inFile into outDir."""
    zipRef = None
    try:
        zipRef = zipfile.ZipFile(inFile, 'r')
        zipRef.extractall(outDir)
    except Exception as e:
        sys.exit("Error extracting zip file: %s" % e)
    finally:
        if zipRef is not None:
            zipRef.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("Usage: %s ZIP_FILE OUTPUT_DIR" % sys.argv[0])
    unzip(sys.argv[1], sys.argv[2])
