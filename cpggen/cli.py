import argparse
import os
import signal
import tempfile
from multiprocessing import Pool
from pathlib import Path

from cpggen import executor, utils
from cpggen.logger import LOG, console

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
        "-i", "--src", dest="src", help="Source directory or url", default=os.getcwd()
    )
    parser.add_argument(
        "-o",
        "--out_dir",
        dest="cpg_out_dir",
        help="CPG output directory",
        default=os.path.join(os.getcwd(), "cpg_out"),
    )
    parser.add_argument(
        "-l",
        "--lang",
        dest="language",
        help="Optional. CPG language frontend to use. Auto-detects by default.",
        choices=[
            "java",
            "java-with-deps",
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
            "kotlin-with-deps",
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
    parser.add_argument(
        "--build",
        dest="auto_build",
        help="Attempt to build the project automatically",
        action="store_true",
        default=True if os.getenv("AUTO_BUILD") in ("true", "1") else False,
    )
    parser.add_argument(
        "--joern-home",
        dest="joern_home",
        help="Joern installation directory",
        default=os.getenv(
            "JOERN_HOME", str(Path.home() / "bin" / "joern" / "joern-cli")
        ),
    )
    return parser.parse_args()


def init_worker():
    """
    Handler for worker processes to let their parent handle interruptions
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def cpg(src, cpg_out_dir, languages, joern_home, use_container=False, auto_build=False):
    if __name__ in ("__main__", "cpggen.cli"):
        with Pool(processes=os.cpu_count(), initializer=init_worker) as pool:
            try:
                for lang in languages:
                    LOG.debug(f"Generating CPG for the language {lang} at {src}")
                    pool.apply_async(
                        executor.exec_tool,
                        (
                            lang,
                            src,
                            cpg_out_dir,
                            src,
                            joern_home,
                            use_container,
                            auto_build,
                        ),
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
    languages = args.language
    joern_home = args.joern_home
    use_container = args.use_container
    if not os.path.exists(joern_home):
        use_container = True
        console.print(
            "Joern installation was not found. Please install joern by following the instructions at https://joern.io and set the environment variable JOERN_HOME to the directory containing the cli tools"
        )
        console.print("Fallback to using cpggen container image")
    is_temp_dir = False
    if src.startswith("http") or src.startswith("git"):
        clone_dir = tempfile.mkdtemp(prefix="cpggen")
        src = utils.clone_repo(src, clone_dir)
        is_temp_dir = True
    if not languages or languages == "autodetect":
        languages = utils.detect_project_type(src)
    else:
        languages = languages.split(",")
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)
    cpg(
        src,
        cpg_out_dir,
        languages,
        joern_home=joern_home,
        use_container=use_container,
        auto_build=args.auto_build,
    )
    if is_temp_dir:
        try:
            os.remove(src)
        except Exception:
            # Ignore cleanup errors
            pass


if __name__ == "__main__":
    main()
