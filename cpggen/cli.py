#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
import signal
import sys
import tempfile
from multiprocessing import Pool, freeze_support
from pathlib import Path, PurePath

from quart import Quart, request

from cpggen import executor, utils
from cpggen.logger import LOG, console, enable_debug

try:
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = 1
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
        default=True
        if (
            os.getenv("AUTO_BUILD") in ("true", "1")
            or os.getenv("SHIFTLEFT_ACCESS_TOKEN")
        )
        else False,
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
        default=os.getenv("CPGGEN_HOST", "0.0.0.0"),
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
        help="Export output directory",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        dest="verbose_mode",
        help="Run cpggen in verbose mode",
    )
    parser.add_argument(
        "--skip-sbom",
        action="store_true",
        default=True
        if not os.getenv("SHIFTLEFT_ACCESS_TOKEN") and not os.getenv("ENABLE_SBOM")
        else False,
        dest="skip_sbom",
        help="Do not generate SBoM",
    )
    parser.add_argument(
        "--slice",
        action="store_true",
        default=True if os.getenv("CPG_SLICE") in ("true", "1") else False,
        dest="slice",
        help="Extract intra-procedural slices from the CPG",
    )
    parser.add_argument(
        "--slice-mode",
        default=os.getenv("CPG_SLICE_MODE", "Usages"),
        dest="slice_mode",
        choices=["Usages", "DataFlow"],
        help="Mode used for CPG slicing",
    )
    parser.add_argument(
        "--use-parse",
        dest="use_parse",
        help="Use joern-parse command instead of invoking the language frontends. Useful when default overlays are important",
        action="store_true",
        default=False,
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
    languages = ""
    cpg_out_dir = None
    is_temp_dir = False
    auto_build = True
    skip_sbom = True
    export = False
    slice = False
    use_parse = False
    slice_mode = "Usages"
    app_manifest_list = []
    errors_warnings = []
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
    if q.get("export", "") in ("true", "1"):
        export = True
    if q.get("slice", "") in ("true", "1"):
        slice = True
    if q.get("slice_mode"):
        slice_mode = q.get("slice_mode")
    if q.get("auto_build", "") in ("false", "0"):
        auto_build = False
    if q.get("skip_sbom", "") in ("false", "0"):
        skip_sbom = False
    if not url and params.get("url"):
        url = params.get("url")
    if not src and params.get("src"):
        src = params.get("src")
    if not languages and params.get("lang"):
        languages = params.get("lang")
    if not cpg_out_dir and params.get("out_dir"):
        cpg_out_dir = params.get("out_dir")
    if params.get("auto_build", "") in ("false", "0"):
        auto_build = False
    if params.get("skip_sbom", "") in ("false", "0"):
        skip_sbom = False
    if params.get("export", "") in ("true", "1"):
        export = True
    if params.get("slice", "") in ("true", "1"):
        slice = True
    if params.get("slice_mode"):
        slice_mode = params.get("slice_mode")
    if not src and not url:
        return {"error": "true", "message": "path or url is required"}, 500
    # If src contains url, then reassign
    if not url and (
        src.startswith("http") or src.startswith("git://") or src.startswith("pkg:")
    ):
        url = src
    if url.startswith("http") or url.startswith("git://") or url.startswith("pkg:"):
        clone_dir = tempfile.mkdtemp(prefix="cpggen")
        if src.startswith("pkg:"):
            download_file = utils.download_package(src, clone_dir)
            if download_file and os.path.exists(download_file):
                src = clone_dir
        else:
            src = utils.clone_repo(url, clone_dir)
        is_temp_dir = True
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)
    if not languages or languages == "autodetect":
        languages = utils.detect_project_type(src)
    else:
        languages = languages.split(",")
    for lang in languages:
        # Use the deps version of the language when using auto build mode
        if lang in ("c", "cpp", "java", "kotlin") and auto_build:
            lang = f"{lang}-with-deps"
        mlist = executor.exec_tool(
            lang,
            src,
            cpg_out_dir,
            src,
            joern_home=os.getenv(
                "JOERN_HOME", str(Path.home() / "bin" / "joern" / "joern-cli")
            ),
            use_container=False,
            use_parse=use_parse,
            auto_build=auto_build,
            extra_args={
                "skip_sbom": skip_sbom,
                "slice_mode": slice_mode,
                "for_export": export,
                "for_slice": slice,
            },
        )
        if mlist:
            app_manifest_list += mlist
        if slice and mlist:
            for ml in mlist:
                if not os.path.exists(ml.get("cpg")):
                    errors_warnings.append(
                        f"""CPG file was not found at {ml.get("cpg")}"""
                    )
                    continue
                executor.exec_tool(
                    "slice",
                    ml.get("cpg"),
                    cpg_out_dir,
                    src,
                    joern_home=os.getenv(
                        "JOERN_HOME", str(Path.home() / "bin" / "joern" / "joern-cli")
                    ),
                    use_container=False,
                    use_parse=use_parse,
                    auto_build=False,
                    extra_args={
                        "slice_mode": slice_mode,
                        "slice_out": ml.get("slice_out"),
                    },
                )
                if not os.path.exists(ml.get("slice_out")):
                    errors_warnings.append(
                        f"""CPG slice file was not found at {ml.get("slice_out")}"""
                    )
    if is_temp_dir:
        try:
            os.remove(src)
        except Exception:
            # Ignore cleanup errors
            pass
    return {
        "success": False if errors_warnings else True,
        "message": "\n".join(errors_warnings)
        if errors_warnings
        else f"CPG generated successfully at {cpg_out_dir}",
        "out_dir": cpg_out_dir,
        "app_manifests": app_manifest_list,
    }


def init_worker():
    """
    Handler for worker processes to let their parent handle interruptions
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def cpg(
    src,
    cpg_out_dir,
    languages,
    joern_home,
    use_container=False,
    use_parse=False,
    auto_build=False,
    skip_sbom=False,
    export=False,
    slice=False,
    slice_mode=None,
):
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
                            use_parse,
                            auto_build,
                            {
                                "skip_sbom": skip_sbom,
                                "slice_mode": slice_mode,
                                "for_export": export,
                                "for_slice": slice,
                            },
                        ),
                    )
                pool.close()
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()


def collect_cpg_manifests(cpg_out_dir):
    return utils.find_files(cpg_out_dir, ".manifest.json")


def fix_export_repr(export_repr, export_format):
    if export_format == "neo4jcsv":
        if export_repr != "cpg":
            LOG.warn(
                "cpg is the only supported export representation for neo4jcsv format"
            )
        return "cpg"
    return export_repr


def export_slice_cpg(
    src,
    cpg_out_dir,
    joern_home,
    use_container,
    use_parse,
    export,
    export_repr,
    export_format,
    export_out_dir,
    slice,
    slice_mode,
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
                        if export:
                            LOG.debug(
                                f"""Exporting CPG for the app {manifest_obj["app"]} from {cpg_path} to {app_export_out_dir}"""
                            )
                        pool.apply_async(
                            executor.exec_tool,
                            (
                                "export" if export else "slice",
                                cpg_path,
                                app_export_out_dir,
                                cpg_out_dir,
                                joern_home,
                                use_container,
                                use_parse,
                                False,
                                {
                                    "export_repr": fix_export_repr(
                                        export_repr, export_format
                                    )
                                    if export
                                    else None,
                                    "export_format": export_format if export else None,
                                    "slice_mode": slice_mode if slice else None,
                                    "slice_out": manifest_obj.get("slice_out"),
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
    # Turn on verbose mode
    if args.verbose_mode:
        enable_debug()
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
            export_out_dir = os.path.join(src, "cpg_export")
    if cpg_out_dir:
        cpg_out_dir = str(PurePath(cpg_out_dir))
    if export_out_dir:
        export_out_dir = str(PurePath(export_out_dir))
    languages = args.language
    joern_home = args.joern_home
    use_container = args.use_container
    use_parse = args.use_parse
    is_bundled_exe = False
    try:
        if getattr(sys, "_MEIPASS"):
            is_bundled_exe = True
            # Reset joern_home for bundled exe
            if not os.path.exists(joern_home):
                joern_home = ""
    except Exception:
        pass
    if joern_home and not os.path.exists(joern_home) and not is_bundled_exe:
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
    if src.startswith("http") or src.startswith("git://") or src.startswith("pkg:"):
        clone_dir = tempfile.mkdtemp(prefix="cpggen")
        if src.startswith("pkg:"):
            download_file = utils.download_package(src, clone_dir)
            if download_file and os.path.exists(download_file):
                src = clone_dir
        else:
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
        use_parse=use_parse,
        auto_build=args.auto_build,
        skip_sbom=args.skip_sbom,
        export=args.export,
        slice=args.slice,
        slice_mode=args.slice_mode,
    )
    if args.export or args.slice:
        export_slice_cpg(
            src,
            cpg_out_dir,
            joern_home=joern_home,
            use_container=use_container,
            use_parse=use_parse,
            export=args.export,
            export_repr=args.export_repr,
            export_format=args.export_format,
            export_out_dir=export_out_dir,
            slice=args.slice,
            slice_mode=args.slice_mode,
        )
    if is_temp_dir:
        try:
            shutil.rmtree(src)
        except Exception:
            # Ignore cleanup errors
            pass


if __name__ == "__main__":
    freeze_support()
    main()
