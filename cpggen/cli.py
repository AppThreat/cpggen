#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
import signal
import tempfile
from multiprocessing import Pool
from pathlib import Path, PurePath

from quart import Quart, request

from cpggen import executor, utils
from cpggen.logger import LOG, console

try:
    os.environ["PYTHONIOENCODING"] = "utf-8"
except Exception:
    pass

product_logo = """
 ██████╗██████╗  ██████╗
██╔════╝██╔══██╗██╔════╝
██║     ██████╔╝██║  ███╗
██║     ██╔═══╝ ██║   ██║
╚██████╗██║     ╚██████╔╝
 ╚═════╝╚═╝      ╚═════╝
"""

app = Quart(__name__)
app.config.from_prefixed_env()


def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(description="CPG Generator")
    parser.add_argument(
        "-i", "--src", dest="src", help="Source directory or url", default=os.getcwd()
    )
    parser.add_argument(
        "-o", "--out-dir", dest="cpg_out_dir", help="CPG output directory"
    )
    parser.add_argument(
        "-l",
        "--lang",
        dest="language",
        help="Optional. CPG language frontend to use. Auto-detects by default.",
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
    parser.add_argument(
        "--server",
        action="store_true",
        default=False,
        dest="server_mode",
        help="Run cpggen as a server",
    )
    parser.add_argument(
        "--server-host",
        default=os.getenv("CPGGEN_HOST", "127.0.0.1"),
        dest="server_host",
        help="cpggen server host",
    )
    parser.add_argument(
        "--server-port",
        default=os.getenv("CPGGEN_PORT", "7072"),
        dest="server_port",
        help="cpggen server port",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        default=True if os.getenv("CPG_EXPORT") in ("true", "1") else False,
        dest="export",
        help="Export CPG as a graph",
    )
    parser.add_argument(
        "--export-repr",
        default=os.getenv("CPG_EXPORT_REPR", "cpg14"),
        dest="export_repr",
        choices=["ast", "cfg", "cdg", "ddg", "pdg", "cpg", "cpg14", "all"],
        help="Graph representation to export",
    )
    parser.add_argument(
        "--export-format",
        default=os.getenv("CPG_EXPORT_FORMAT", "dot"),
        dest="export_format",
        choices=["neo4jcsv", "graphml", "graphson", "dot"],
        help="Export format",
    )
    parser.add_argument(
        "--export-out-dir",
        dest="export_out_dir",
        help="Export output directoru",
    )
    return parser.parse_args()


@app.get("/")
async def index():
    return {}


def run_server(args):
    console.print(product_logo, style="info")
    console.print(f"cpggen server running on {args.server_host}:{args.server_port}")
    app.run(
        host=args.server_host,
        port=args.server_port,
        debug=True if os.getenv("AT_DEBUG_MODE") in ("debug", "true", "1") else False,
        use_reloader=False,
    )


@app.route("/cpg", methods=["GET", "POST"])
async def generate_cpg():
    q = request.args
    params = await request.get_json()
    url = ""
    src = ""
    languages = "autodetect"
    cpg_out_dir = None
    is_temp_dir = False
    if not params:
        params = {}
    if q.get("url"):
        url = q.get("url")
    if q.get("src"):
        src = q.get("src")
    if q.get("out_dir"):
        cpg_out_dir = q.get("out_dir")

    if q.get("lang"):
        languages = q.get("lang")
    if not url and params.get("url"):
        url = params.get("url")
    if not src and params.get("src"):
        src = params.get("src")
    if not languages and params.get("lang"):
        languages = params.get("lang")
    if not cpg_out_dir and params.get("out_dir"):
        cpg_out_dir = params.get("out_dir")
    if not src and not url:
        return {"error": "true", "message": "path or url is required"}, 500
    if url.startswith("http") or url.startswith("git"):
        clone_dir = tempfile.mkdtemp(prefix="cpggen")
        src = utils.clone_repo(url, clone_dir)
        is_temp_dir = True
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)
    if not languages or languages == "autodetect":
        languages = utils.detect_project_type(src)
    else:
        languages = languages.split(",")
    for lang in languages:
        executor.exec_tool(
            lang,
            src,
            cpg_out_dir,
            src,
            joern_home=os.getenv(
                "JOERN_HOME", str(Path.home() / "bin" / "joern" / "joern-cli")
            ),
        )
    if is_temp_dir:
        try:
            os.remove(src)
        except Exception:
            # Ignore cleanup errors
            pass
    return {
        "success": True,
        "message": f"CPG generated successfully at {cpg_out_dir}",
        "out_dir": cpg_out_dir,
    }


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
                            {},
                        ),
                    )
                pool.close()
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()


def collect_cpg_manifests(cpg_out_dir):
    return utils.find_files(cpg_out_dir, ".manifest.json")


def export_cpg(
    src,
    cpg_out_dir,
    joern_home,
    use_container,
    export_repr,
    export_format,
    export_out_dir,
):
    if __name__ in ("__main__", "cpggen.cli"):
        with Pool(processes=os.cpu_count(), initializer=init_worker) as pool:
            try:
                cpg_manifests = collect_cpg_manifests(cpg_out_dir)
                for amanifest in cpg_manifests:
                    with open(amanifest) as mfp:
                        manifest_obj = json.load(mfp)
                        if not manifest_obj or not manifest_obj.get("cpg"):
                            continue
                        app_export_out_dir = os.path.join(
                            export_out_dir, manifest_obj["app"]
                        )
                        try:
                            # joern-export annoyingly will not overwrite directories
                            # but would expect first level directories to exist
                            if os.path.exists(app_export_out_dir):
                                try:
                                    shutil.rmtree(app_export_out_dir)
                                except Exception:
                                    # Ignore remove errors
                                    pass
                            os.makedirs(export_out_dir, exist_ok=True)
                        except Exception:
                            # Ignore errors
                            pass
                        cpg_path = manifest_obj["cpg"]
                        # In case of GitHub action we need to fix the cpg_path to prefix GITHUB_WORKSPACE
                        # since the manifest would only have relative path
                        if os.getenv("GITHUB_WORKSPACE") and not cpg_path.startswith(
                            os.getenv("GITHUB_WORKSPACE")
                        ):
                            cpg_path = os.path.join(
                                os.getenv("GITHUB_WORKSPACE"), cpg_path
                            )
                        LOG.debug(
                            f"""Exporting CPG for the app {manifest_obj["app"]} from {cpg_path} to {app_export_out_dir}"""
                        )
                        pool.apply_async(
                            executor.exec_tool,
                            (
                                "export",
                                cpg_path,
                                app_export_out_dir,
                                cpg_out_dir,
                                joern_home,
                                use_container,
                                False,
                                {
                                    "export_repr": export_repr,
                                    "export_format": export_format,
                                },
                            ),
                        )
                pool.close()
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()


def main():
    print(product_logo)
    args = build_args()
    if args.server_mode:
        return run_server(args)
    src = args.src
    cpg_out_dir = args.cpg_out_dir
    export_out_dir = args.export_out_dir
    if not src.startswith("http") and not src.startswith("git://"):
        src = str(PurePath(args.src))
        if not cpg_out_dir and src:
            if os.path.isfile(src):
                cpg_out_dir = os.path.join(os.path.dirname(src), "cpg_out")
            else:
                cpg_out_dir = os.path.join(src, "cpg_out")
        if not export_out_dir and src:
            export_out_dir = os.path.join(src, "export_out")
    if cpg_out_dir:
        cpg_out_dir = str(PurePath(cpg_out_dir))
    if export_out_dir:
        export_out_dir = str(PurePath(export_out_dir))
    languages = args.language
    joern_home = args.joern_home
    use_container = args.use_container
    if joern_home and not os.path.exists(joern_home):
        if utils.check_command("docker") or utils.check_command("podman"):
            use_container = True
        else:
            console.print(
                "Joern installation was not found. Please install joern by following the instructions at https://joern.io and set the environment variable JOERN_HOME to the directory containing the cli tools"
            )
            console.print(
                "Alternatively, ensure docker or podman is available to use cpggen container image"
            )
    # GitHub action is very weird
    if os.getenv("GITHUB_PATH") and utils.check_command("joern"):
        joern_home = ""
    is_temp_dir = False
    if src.startswith("http") or src.startswith("git://"):
        clone_dir = tempfile.mkdtemp(prefix="cpggen")
        src = utils.clone_repo(src, clone_dir)
        is_temp_dir = True
        if not cpg_out_dir:
            cpg_out_dir = tempfile.mkdtemp(prefix="cpggen_cpg_out")
        if not export_out_dir:
            export_out_dir = tempfile.mkdtemp(prefix="cpggen_export_out")
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
    if args.export:
        export_cpg(
            src,
            cpg_out_dir,
            joern_home=joern_home,
            use_container=use_container,
            export_repr=args.export_repr,
            export_format=args.export_format,
            export_out_dir=export_out_dir,
        )
    if is_temp_dir:
        try:
            shutil.rmtree(src)
        except Exception:
            # Ignore cleanup errors
            pass


if __name__ == "__main__":
    main()
