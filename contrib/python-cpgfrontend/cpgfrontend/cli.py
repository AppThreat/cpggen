import argparse
import os
import shutil
import signal
import sys
import tempfile
from multiprocessing import Pool, freeze_support
from pathlib import Path, PurePath

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

if __name__ == "__main__":
    freeze_support()
    main()
