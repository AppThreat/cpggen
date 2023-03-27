import argparse
import os
import signal
import tempfile
from multiprocessing import Pool

from cpggen import executor, utils
from cpggen.logger import console

product_logo = """
 ██████╗██████╗  ██████╗
██╔════╝██╔══██╗██╔════╝
██║     ██████╔╝██║  ███╗
██║     ██╔═══╝ ██║   ██║
╚██████╗██║     ╚██████╔╝
 ╚═════╝╚═╝      ╚═════╝
"""


def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(description="CPG Generator")
    parser.add_argument(
        "-i", "--src", dest="src", help="Source directory or url", default="/app"
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
            "dotnet",
            "binary",
            "javascript",
            "js",
            "jsp",
            "scala",
            "typescript",
            "ts",
            "python",
            "php",
            "kotlin",
            "llvm",
            "autodetect",
        ],
        default="autodetect",
    )
    parser.add_argument(
        "--use-container",
        dest="use_container",
        help="Use cpggen docker image",
        action="store_true",
        default=False,
    )
    return parser.parse_args()


def init_worker():
    """
    Handler for worker processes to let their parent handle interruptions
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def cpg(src, cpg_out_dir, language, use_container=False):
    if __name__ in ("__main__", "cpggen.cli"):
        with Pool(processes=os.cpu_count(), initializer=init_worker) as pool:
            try:
                for lang in language:
                    pool.apply_async(
                        executor.exec_tool, (lang, src, cpg_out_dir, src, use_container)
                    )
                pool.close()
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()


def main():
    console.print(product_logo, style="info")
    args = build_args()
    src = args.src
    cpg_out_dir = args.cpg_out_dir
    language = args.language
    is_temp_dir = False
    if not language or language == "autodetect":
        language = utils.detect_project_type(src)
    else:
        language = language.split(",")
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)
    if src.startswith("http") or src.startswith("git"):
        clone_dir = tempfile.TemporaryDirectory(prefix="cpggen")
        src = utils.clone_repo(src, clone_dir)
        is_temp_dir = True
    cpg(src, cpg_out_dir, language, use_container=args.use_container)
    if is_temp_dir:
        os.remove(src)


if __name__ == "__main__":
    main()
