import argparse
import os
import shutil
import signal
import sys
import tempfile
from multiprocessing import Pool, freeze_support
from pathlib import Path, PurePath
from cpgfrontend.lib.cpg import *
from zipfile import ZipFile

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(description="CPG frontend")
    parser.add_argument(
        "-i",
        "--src",
        dest="src",
        help="Source directory or file",
        default=os.getcwd(),
    )
    parser.add_argument(
        "-o", "--out-dir", dest="cpg_out_dir", help="CPG output directory"
    )
    return parser.parse_args()

def main():
    """Main method"""
    args = build_args()

    methodFullName = CpgStructNodeProperty(
        name=NodePropertyName.FULL_NAME,
        value=PropertyValue("main")
    )

    method = CpgStructNode(
        key=1,
        type=CpgStructNodeNodeType.METHOD,
        property=[methodFullName]
    )

    cpg = CpgStruct(node=[method])
    cpg_file = persist(cpg)

def persist(cpg, file_name = "cpg.bin.zip"):
    """persist cpg (of type CpgStruct) to disk, e.g. so you can open it in joern:
    joern> importCpg("/path/to/cpg.bin.zip")
    """
    with ZipFile(file_name, "w") as zip_file:
        zip_file.writestr("cpg.proto", bytes(cpg))

if __name__ == "__main__":
    freeze_support()
    main()
