#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
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

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

PRODUCT_LOGO = """
 ██████╗██████╗  ██████╗
██╔════╝██╔══██╗██╔════╝
██║     ██████╔╝██║  ███╗
██║     ██╔═══╝ ██║   ██║
╚██████╗██║     ╚██████╔╝
 ╚═════╝╚═╝      ╚═════╝
"""

ATOM_LOGO = """
 █████╗ ████████╗ ██████╗ ███╗   ███╗
██╔══██╗╚══██╔══╝██╔═══██╗████╗ ████║
███████║   ██║   ██║   ██║██╔████╔██║
██╔══██║   ██║   ██║   ██║██║╚██╔╝██║
██║  ██║   ██║   ╚██████╔╝██║ ╚═╝ ██║
╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
"""

app = Quart(__name__)
app.config.from_prefixed_env()


def build_args():
    """
    Constructs command line arguments for the scanner
    """
    parser = argparse.ArgumentParser(description="CPG Generator")
    parser.add_argument(
        "-i",
        "--src",
        dest="src",
        help="Source directory or url or CVE or GHSA id",
        default=os.getcwd(),
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
        default=os.getenv("AUTO_BUILD") in ("true", "1")
        or os.getenv("SHIFTLEFT_ACCESS_TOKEN"),
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
        default=os.getenv("CPG_EXPORT") in ("true", "1"),
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
        default=not os.getenv("SHIFTLEFT_ACCESS_TOKEN")
        and not os.getenv("ENABLE_SBOM"),
        dest="skip_sbom",
        help="Do not generate SBoM",
    )
    parser.add_argument(
        "--slice",
        action="store_true",
        default=os.getenv("CPG_SLICE") in ("true", "1"),
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
        "--use-atom",
        dest="use_atom",
        help="Use atom toolkit",
        action="store_true",
        default=os.getenv("USE_ATOM") in ("true", "1"),
    )
    parser.add_argument(
        "--vectors",
        action="store_true",
        default=os.getenv("CPG_VECTORS") in ("true", "1"),
        dest="vectors",
        help="Extract vector representations of code from CPG",
    )
    return parser.parse_args()


@app.get("/")
async def index():
    """Index route"""
    return {}


def run_server(args):
    """Run cpggen as a server"""
    console.print(f"cpggen server running on {args.server_host}:{args.server_port}")
    app.run(
        host=args.server_host,
        port=args.server_port,
        debug=os.getenv("AT_DEBUG_MODE") in ("debug", "true", "1"),
        use_reloader=False,
    )


@app.route("/cpg", methods=["GET", "POST"])
async def generate_cpg():
    """Method to generate CPG via the http route"""
    q = request.args
    params = await request.get_json()
    url = ""
    src = ""
    languages = ""
    cpg_out_dir = None
    auto_build = True
    skip_sbom = True
    export = False
    should_slice = False
    use_atom = False
    slice_mode = "Usages"
    app_manifest_list = []
    errors_warnings = []
    vectors = False
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
    if q.get("export", "") in ("True", "true", "1"):
        export = True
    if q.get("slice", "") in ("True", "true", "1"):
        should_slice = True
    if q.get("vectors", "") in ("True", "true", "1"):
        vectors = True
    if q.get("slice_mode"):
        slice_mode = q.get("slice_mode")
    if q.get("auto_build", "") in ("False", "false", "0"):
        auto_build = False
    if q.get("skip_sbom", "") in ("False", "false", "0"):
        skip_sbom = False
    if not url and params.get("url"):
        url = params.get("url")
    if not src and params.get("src"):
        src = params.get("src")
    if not languages and params.get("lang"):
        languages = params.get("lang")
    if not cpg_out_dir and params.get("out_dir"):
        cpg_out_dir = params.get("out_dir")
    if params.get("auto_build", "") in ("False", "false", "0"):
        auto_build = False
    if params.get("skip_sbom", "") in ("False", "false", "0"):
        skip_sbom = False
    if params.get("export", "") in ("True", "true", "1"):
        export = True
    if params.get("slice", "") in ("True", "true", "1"):
        should_slice = True
    if params.get("vectors", "") in ("True", "true", "1"):
        vectors = True
    if params.get("slice_mode"):
        slice_mode = params.get("slice_mode")
    if not src and not url:
        return {"error": "true", "message": "path or url is required"}, 500
    # If src contains url, then reassign
    if not src and url:
        src = url
    if not os.path.exists(src):
        clone_dir = tempfile.mkdtemp(prefix="cpggen")
        if src.startswith("http") or src.startswith("git://"):
            utils.clone_repo(url, clone_dir)
        else:
            utils.download_package_unsafe(url, clone_dir)
        src = clone_dir
    if not cpg_out_dir:
        cpg_out_dir = tempfile.mkdtemp(prefix="cpggen_cpg_out")
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)
    if not languages or languages == "autodetect":
        languages = utils.detect_project_type(src)
    else:
        languages = languages.split(",")
    for lang in languages:
        mlist = executor.exec_tool(
            lang,
            src,
            cpg_out_dir,
            src,
            joern_home=os.getenv(
                "JOERN_HOME", str(Path.home() / "bin" / "joern" / "joern-cli")
            ),
            use_container=False,
            use_atom=use_atom,
            auto_build=auto_build,
            extra_args={
                "skip_sbom": skip_sbom,
                "slice_mode": slice_mode,
                "for_export": export,
                "for_slice": should_slice,
                "for_vectors": vectors,
                "url": url,
            },
        )
        if mlist:
            app_manifest_list += mlist
        if should_slice and mlist:
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
                    use_atom=use_atom,
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


def get_output_dir(src, cpg_out_dir=None, export_out_dir=None):
    """Method to determine and create the cpg and export output directories"""
    if not src:
        return None, None, False
    is_temp_dir = False
    # purl, http url or CVE id
    if not os.path.exists(src):
        if not cpg_out_dir:
            cpg_out_dir = tempfile.mkdtemp(prefix="cpggen_cpg_out")
            is_temp_dir = True
        if not export_out_dir:
            export_out_dir = tempfile.mkdtemp(prefix="cpggen_export_out")
            is_temp_dir = True
    if not cpg_out_dir:
        if os.path.isfile(src):
            cpg_out_dir = os.path.join(os.path.dirname(src), "cpg_out")
        else:
            cpg_out_dir = os.path.join(src, "cpg_out")
    if not export_out_dir:
        export_out_dir = os.path.join(src, "cpg_export")
    cpg_out_dir = str(PurePath(cpg_out_dir))
    export_out_dir = str(PurePath(export_out_dir))
    if cpg_out_dir and not os.path.exists(cpg_out_dir):
        os.makedirs(cpg_out_dir, exist_ok=True)
    return cpg_out_dir, export_out_dir, is_temp_dir


def cpg(
    src,
    cpg_out_dir,
    languages,
    joern_home,
    use_container=False,
    use_atom=False,
    auto_build=False,
    skip_sbom=False,
    export=False,
    should_slice=False,
    slice_mode=None,
    vectors=False,
):
    """Method to generate cpg using multiple processes"""
    if __name__ in ("__main__", "cpggen.cli"):
        with Pool(processes=os.cpu_count(), initializer=init_worker) as pool:
            try:
                ret = []
                exec_results = []
                url = ""
                # Where the source is a url or a CVE id download it
                if not os.path.isdir(src) and not os.path.isfile(src):
                    url = src
                    clone_dir = tempfile.mkdtemp(prefix="cpggen")
                    if src.startswith("http") or src.startswith("git://"):
                        utils.clone_repo(src, clone_dir)
                    else:
                        utils.download_package_unsafe(src, clone_dir)
                    src = clone_dir
                if not languages or languages == "autodetect":
                    languages = utils.detect_project_type(src)
                else:
                    languages = languages.split(",")
                for lang in languages:
                    LOG.debug("Generating CPG for the language %s at %s", lang, src)
                    exec_results.append(
                        pool.apply_async(
                            executor.exec_tool,
                            (
                                lang,
                                src,
                                cpg_out_dir,
                                src,
                                joern_home,
                                use_container,
                                use_atom,
                                auto_build,
                                {
                                    "skip_sbom": skip_sbom,
                                    "slice_mode": slice_mode,
                                    "for_export": export,
                                    "for_slice": should_slice,
                                    "for_vectors": vectors,
                                    "url": url,
                                },
                            ),
                        )
                    )
                for res in exec_results:
                    manifests_list = res.get()
                    if manifests_list:
                        ret += manifests_list
                pool.close()
                return ret
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()
    return None


def fix_export_repr(export_repr, export_format):
    """Method to validate and fix the export representation based on the format"""
    if export_format == "neo4jcsv":
        if export_repr != "cpg":
            LOG.warning(
                "cpg is the only supported export representation for neo4jcsv format"
            )
        return "cpg"
    return export_repr


def export_slice_cpg(
    cpg_out_dir,
    joern_home,
    use_container,
    use_atom,
    export,
    export_repr,
    export_format,
    export_out_dir,
    should_slice=False,
    slice_mode=None,
    vectors=False,
    cpg_manifests=None,
):
    """Method to export or slice cpg"""
    if __name__ in ("__main__", "cpggen.cli"):
        with Pool(processes=os.cpu_count(), initializer=init_worker) as pool:
            try:
                export_tool = "export"
                if should_slice:
                    export_tool = "slice"
                elif vectors:
                    export_tool = "vectors"
                # Collect the CPG manifests if none was provided.
                # This could result in duplicate executions
                if not cpg_manifests:
                    cpg_manifests = utils.collect_cpg_manifests(cpg_out_dir)
                for manifest_obj in cpg_manifests:
                    if not manifest_obj or not manifest_obj.get("cpg"):
                        continue
                    app_export_out_dir = os.path.join(
                        export_out_dir, manifest_obj["app"]
                    )
                    # joern-export annoyingly will not overwrite directories
                    # but would expect first level directories to exist
                    if os.path.exists(app_export_out_dir):
                        shutil.rmtree(app_export_out_dir, ignore_errors=True)
                    os.makedirs(app_export_out_dir, exist_ok=True)
                    cpg_path = manifest_obj["cpg"]
                    # In case of GitHub action we need to fix the cpg_path to prefix GITHUB_WORKSPACE
                    # since the manifest would only have relative path
                    if os.getenv("GITHUB_WORKSPACE") and not cpg_path.startswith(
                        os.getenv("GITHUB_WORKSPACE")
                    ):
                        cpg_path = os.path.join(os.getenv("GITHUB_WORKSPACE"), cpg_path)
                    if export:
                        LOG.debug(
                            """Exporting CPG for the app %s from %s to %s""",
                            manifest_obj["app"],
                            cpg_path,
                            app_export_out_dir,
                        )
                    pool.apply_async(
                        executor.exec_tool,
                        (
                            export_tool,
                            cpg_path,
                            app_export_out_dir,
                            cpg_out_dir,
                            joern_home,
                            use_container,
                            use_atom,
                            False,
                            {
                                "export_repr": fix_export_repr(
                                    export_repr, export_format
                                )
                                if export
                                else None,
                                "export_format": export_format if export else None,
                                "slice_mode": slice_mode if should_slice else None,
                                "slice_out": manifest_obj.get("slice_out"),
                            },
                        ),
                    )
                pool.close()
            except KeyboardInterrupt:
                pool.terminate()
            pool.join()


def main():
    """Main method"""
    if os.getenv("ATOM_HOME"):
        print(ATOM_LOGO)
    else:
        print(PRODUCT_LOGO)
    args = build_args()
    # Turn on verbose mode
    if args.verbose_mode:
        enable_debug()
    if args.server_mode:
        return run_server(args)
    src = args.src
    cpg_out_dir, export_out_dir, is_temp_dir = get_output_dir(
        src, args.cpg_out_dir, args.export_out_dir
    )
    if os.path.exists(src):
        src = str(PurePath(src))
    joern_home = args.joern_home
    use_container = args.use_container
    use_atom = args.use_atom
    is_bundled_exe = False
    try:
        if getattr(sys, "_MEIPASS"):
            is_bundled_exe = True
            # Reset joern_home for bundled exe
            if not os.path.exists(joern_home):
                joern_home = ""
    except AttributeError:
        pass
    # GitHub action is very weird
    if os.getenv("GITHUB_PATH") and utils.check_command("joern"):
        joern_home = ""
    cpg_manifests = cpg(
        src,
        cpg_out_dir,
        args.language,
        joern_home=joern_home,
        use_container=use_container,
        use_atom=use_atom,
        auto_build=args.auto_build,
        skip_sbom=args.skip_sbom,
        export=args.export,
        should_slice=args.slice,
        slice_mode=args.slice_mode,
        vectors=args.vectors,
    )
    if args.export or args.slice or args.vectors:
        export_slice_cpg(
            cpg_out_dir,
            joern_home=joern_home,
            use_container=use_container,
            use_atom=use_atom,
            export=args.export,
            export_repr=args.export_repr,
            export_format=args.export_format,
            export_out_dir=export_out_dir,
            should_slice=args.slice,
            slice_mode=args.slice_mode,
            vectors=args.vectors,
            cpg_manifests=cpg_manifests,
        )
    # We can remove the src but not the cpg_out and cpg_export which might get used
    # by downstream tools
    if is_temp_dir and src.startswith(tempfile.gettempdir()):
        shutil.rmtree(src, ignore_errors=True)


if __name__ == "__main__":
    freeze_support()
    main()
