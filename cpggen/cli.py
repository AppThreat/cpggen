import argparse
import os
import signal
import sys
import tempfile
import time
import uuid
from multiprocessing import Pool
from pathlib import Path


def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(description="CPG Generator")
    parser.add_argument(
        "-i", "--src", dest="src_dir", help="Source directory", default="/app"
    )
    parser.add_argument(
        "-o",
        "--out_dir",
        dest="cpg_out_dir",
        help="CPG output directory",
        default="/app/cpg_out",
    )
    parser.add_argument(
        "-l",
        "--lang",
        dest="language",
        help="Optional. CPG language frontend to use. Auto-detects by default.",
        choices=[
            "java",
            "jar",
            "c",
            "cpp",
            "go",
            "csharp",
            "binary",
            "js",
            "ts",
            "python",
            "php",
            "kotlin",
            "llvm",
        ],
    )
    return parser.parse_args()


def main():
    args = build_args()
    src_dir = args.src_dir
    cpg_out_dir = args.cpg_out_dir
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)


if __name__ == "__main__":
    main()
