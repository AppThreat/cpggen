import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath

import psutil
from psutil._common import bytes2human
from rich.progress import Progress

from cpggen.logger import DEBUG, LOG, console
from cpggen.utils import (
    check_command,
    find_csharp_artifacts,
    find_files,
    find_go_mods,
    find_gradle_files,
    find_java_artifacts,
    find_makefiles,
    find_pom_files,
    find_sbt_files,
    purl_to_friendly_name,
)

runtimeValues = {}
svmem = psutil.virtual_memory()
max_memory = bytes2human(getattr(svmem, "available"), format="%(value).0f%(symbol)s")
CPU_COUNT = str(psutil.cpu_count())

only_bat_ext = ".bat" if sys.platform == "win32" else ""
bin_ext = ".bat" if sys.platform == "win32" else ".sh"
exe_ext = ".exe" if sys.platform == "win32" else ""
USE_SHELL = True if sys.platform == "win32" else False

ATOM_VERSION = "1.0.0"
ATOM_CMD = "atom"

try:
    import importlib.resources

    # Defeat lazy module importers.
    importlib.resources.open_text
    HAVE_RESOURCE_READER = True
except ImportError:
    HAVE_RESOURCE_READER = False

atom_dir = None
atom_exploded = None
if HAVE_RESOURCE_READER:
    try:
        res_atom_dir = importlib.resources.contents("cpggen.atom")
        zfiles = [rf for rf in res_atom_dir if rf == "atom.zip"]
        if zfiles:
            atom_dir = (Path(__file__).parent / "atom" / zfiles[0]).parent.absolute()
    except Exception:
        pass
else:
    atom_dir = (Path(__file__).parent / "atom").absolute()

if atom_dir:
    atom_bundled = os.path.join(atom_dir, "atom.zip")
    atom_exploded = os.path.join(atom_dir, f"atom-{ATOM_VERSION}")

# Extract bundled atom
if atom_dir and not os.path.exists(atom_exploded) and os.path.exists(atom_bundled):
    try:
        with zipfile.ZipFile(atom_bundled, "r") as zip_ref:
            zip_ref.extractall(atom_dir)
            os.chmod(os.path.join(atom_exploded, "bin", ATOM_CMD), 0o755)
            LOG.debug("Extracted %s to %s", atom_bundled, atom_exploded)
    except Exception as e:
        LOG.error(e)

if atom_exploded and os.path.exists(atom_exploded) and not os.getenv("ATOM_HOME"):
    os.environ["ATOM_HOME"] = atom_exploded
    os.environ["ATOM_BIN_DIR"] = os.path.join(atom_exploded, "bin", "")
    os.environ["PATH"] = (
        os.environ["PATH"] + os.pathsep + os.environ["ATOM_BIN_DIR"] + os.pathsep
    )


def resource_path(relative_path):
    """Function to construct the path to resources in a bundled exe"""
    try:
        base_path = getattr(sys, "_MEIPASS")
    except AttributeError:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


# Check if we are running as a bundled executable and
# extract the binaries
cdxgen_cmd = os.environ.get("CDXGEN_CMD", "cdxgen")
local_bin_dir = resource_path("local_bin")
if os.path.exists(local_bin_dir):
    csharp2cpg_bundled = resource_path(
        os.path.join("local_bin", f"atom-{ATOM_VERSION}", "csharp2cpg.zip")
    )
    atom_bundled = resource_path(os.path.join("local_bin", "atom.zip"))
    if os.path.exists(csharp2cpg_bundled) and not os.path.exists(
        os.path.join(local_bin_dir, f"atom-{ATOM_VERSION}", "bin", "csharp2cpg")
    ):
        try:
            with zipfile.ZipFile(csharp2cpg_bundled, "r") as zip_ref:
                zip_ref.extractall(os.path.join(local_bin_dir, f"atom-{ATOM_VERSION}"))
                LOG.debug(
                    "Extracted %s to %s",
                    csharp2cpg_bundled,
                    os.path.join(local_bin_dir, f"atom-{ATOM_VERSION}"),
                )
                if not os.path.exists(
                    os.path.join(
                        local_bin_dir, f"atom-{ATOM_VERSION}", "bin", "csharp2cpg"
                    )
                ):
                    LOG.debug("csharp2cpg could not be found after extraction")
        except Exception as e:
            LOG.info(
                "cpggen was prevented from extracting the csharp2cpg frontend.\nPlease check if your terminal has administrative privileges or if the antivirus is preventing this process.\nAlternatively, use container-based execution."
            )
            LOG.error(e)
    if os.path.exists(atom_bundled) and not os.path.exists(
        os.path.join(local_bin_dir, f"atom-{ATOM_VERSION}", "bin", "atom")
    ):
        try:
            with zipfile.ZipFile(atom_bundled, "r") as zip_ref:
                zip_ref.extractall(local_bin_dir)
                # Add execute permissions
                for dirname, subdirs, files in os.walk(local_bin_dir):
                    for filename in files:
                        if (
                            not filename.endswith(".zip")
                            and not filename.endswith(".jar")
                            and not filename.endswith(".json")
                            and not filename.endswith(".dll")
                            and (
                                filename.endswith("%(bin_ext)s")
                                or "2cpg" in filename
                                or "joern-" in filename
                                or "atom" in filename
                            )
                        ):
                            os.chmod(os.path.join(dirname, filename), 0o755)
                LOG.debug("Extracted %s to %s", atom_bundled, local_bin_dir)
                os.environ["ATOM_HOME"] = os.path.join(
                    local_bin_dir, f"atom-{ATOM_VERSION}"
                )
                os.environ["ATOM_BIN_DIR"] = os.path.join(
                    local_bin_dir, f"atom-{ATOM_VERSION}", "bin", ""
                )
                os.environ["CPGGEN_BIN_DIR"] = local_bin_dir
                os.environ["PATH"] = (
                    os.environ["PATH"]
                    + os.pathsep
                    + os.environ["ATOM_BIN_DIR"]
                    + os.pathsep
                    + os.environ["CPGGEN_BIN_DIR"]
                    + os.pathsep
                )
        except Exception as e:
            LOG.info(
                "cpggen was prevented from extracting the atom library.\nPlease check if your terminal has administrative privileges or if the antivirus is preventing this process.\nAlternatively, use container-based execution."
            )
            LOG.error(e)
    if not shutil.which(cdxgen_cmd):
        local_cdxgen_cmd = resource_path(
            os.path.join(
                "local_bin", "cdxgen.exe" if sys.platform == "win32" else "cdxgen"
            )
        )
        if os.path.exists(local_cdxgen_cmd):
            cdxgen_cmd = local_cdxgen_cmd
            # Set the plugins directory as an environment variable
            os.environ["CDXGEN_PLUGINS_DIR"] = local_bin_dir


def get(config_name, default_value=None):
    """Method to retrieve a config given a name. This method lazy loads configuration
    values and helps with overriding using a local config
    :param config_name: Name of the config
    :return Config value
    """
    value = runtimeValues.get(config_name)
    if value is None:
        value = os.environ.get(config_name.replace("-", "_").upper())
    if value is None:
        value = default_value
    return value


cpg_tools_map = {
    "atom": "%(atom_bin_dir)satom --language %(parse_lang)s --withDataDeps --slice -m %(slice_mode)s --slice-outfile %(slice_out)s --output %(atom_out)s %(src)s",
    "c": "%(joern_home)sc2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "cpp": "%(joern_home)sc2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "c-with-deps": "%(joern_home)sc2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "cpp-with-deps": "%(joern_home)sc2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "java": "%(joern_home)sjavasrc2cpg%(only_bat_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "java-with-deps": "%(joern_home)sjavasrc2cpg%(only_bat_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --fetch-dependencies --inference-jar-paths %(home_dir)s/.m2",
    "java-with-gradle-deps": "%(joern_home)sjavasrc2cpg%(only_bat_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --fetch-dependencies --inference-jar-paths %(home_dir)s/.gradle/caches/modules-2/files-2.1",
    "jimple": "%(joern_home)sjimple2cpg%(only_bat_ext)s%(android_jar)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "binary": "%(joern_home)sghidra2cpg%(only_bat_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "js": "%(joern_home)sjssrc2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "kotlin": "%(joern_home)skotlin2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "kotlin-with-deps": "%(joern_home)skotlin2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --download-dependencies",
    "kotlin-with-classpath": "%(joern_home)skotlin2cpg%(bin_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --classpath %(home_dir)s/.m2 --classpath %(home_dir)s/.gradle/caches/modules-2/files-2.1",
    "php": "%(joern_home)sphp2cpg%(only_bat_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "python": "%(joern_home)spysrc2cpg%(only_bat_ext)s -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "sbom": "%(cdxgen_cmd)s%(exe_ext)s%(cdxgen_args)s -r -t %(tool_lang)s -o %(sbom_out)s %(src)s",
    "parse": "%(joern_home)sjoern-parse%(only_bat_ext)s -J-Xmx%(memory)s --language %(parse_lang)s --output %(cpg_out)s %(src)s",
    "vectors": "%(joern_home)sjoern-vectors%(only_bat_ext)s -J-Xmx%(memory)s --out %(cpg_out)s %(src)s",
    "export": "%(joern_home)sjoern-export%(only_bat_ext)s -J-Xmx%(memory)s --repr=%(export_repr)s --format=%(export_format)s --out %(cpg_out)s %(src)s",
    "slice": "%(atom_bin_dir)satom --language %(parse_lang)s --withDataDeps --slice -m %(slice_mode)s --slice-outfile %(slice_out)s --output %(atom_out)s %(src)s",
    "dot2png": "dot -Tpng %(dot_file)s -o %(png_out)s",
}

cpg_tools_map["npm"] = cpg_tools_map["js"]
cpg_tools_map["ts"] = cpg_tools_map["js"]
cpg_tools_map["javascript"] = cpg_tools_map["js"]
cpg_tools_map["typescript"] = cpg_tools_map["js"]
cpg_tools_map["maven"] = cpg_tools_map["jimple"]
cpg_tools_map["jar"] = cpg_tools_map["jimple"]
cpg_tools_map["pypi"] = cpg_tools_map["python"]

build_tools_map = {
    "csharp": ["dotnet", "build"],
    "java-with-deps": {
        "maven": [
            get("MVN_CMD", "%(maven_cmd)s"),
            "compile",
        ],
        "gradle": [get("GRADLE_CMD", "%(gradle_cmd)s"), "compileJava"],
        "sbt": ["sbt", "stage"],
    },
    "jar": {
        "maven": [
            get("MVN_CMD", "%(maven_cmd)s"),
            "compile",
            "package",
            "-Dmaven.test.skip=true",
        ],
        "gradle": [get("GRADLE_CMD", "%(gradle_cmd)s"), "jar"],
        "sbt": ["sbt", "stage"],
    },
    "android": {"gradle": [get("GRADLE_CMD", "%(gradle_cmd)s"), "compileDebugSources"]},
    "kotlin": {
        "maven": [
            get("MVN_CMD", "%(maven_cmd)s"),
            "compile",
            "package",
            "-Dmaven.test.skip=true",
        ],
        "gradle": [get("GRADLE_CMD", "gradle"), "build"],
    },
    "scala": ["sbt", "stage"],
    "go": {
        "go": ["go", "build", "./..."],
        "make": ["make"],
        "mage": ["mage", "build"],
    },
    "php": {
        "init": ["composer", "init", "--quiet"],
        "install": ["composer", "install", "-n", "--ignore-platform-reqs"],
        "update": ["composer", "update", "-n", "--ignore-platform-reqs"],
        "autoload": ["composer", "dump-autoload", "-o"],
    },
    "make": ["make"],
}

joern_parse_lang_map = {
    "jar": "javasrc",
    "jsp": "javasrc",
    "scala": "javasrc",
    "java": "javasrc",
    "python": "pythonsrc",
    "js": "jssrc",
    "ts": "jssrc",
    "javascript": "jssrc",
    "typescript": "jssrc",
    "cpp": "newc",
    "c": "newc",
    "binary": "ghidra",
    "ruby": "rubysrc",
}


def dot_convert(export_out_dir, env):
    """Method to convert .dot files to png format using dot command"""
    if check_command("dot"):
        dot_files = find_files(export_out_dir, ".dot", False, False)
        if len(dot_files) > 5:
            LOG.info(
                "%d dot files generated after export. Skipping dot2png conversion ...",
                len(dot_files),
            )
            return
        for df in dot_files:
            convert_cmd_with_args = cpg_tools_map["dot2png"] % dict(
                dot_file=df, png_out=df.replace(".dot", ".png")
            )
            try:
                subprocess.run(
                    convert_cmd_with_args.split(" "),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=export_out_dir,
                    env=env,
                    check=False,
                    shell=USE_SHELL,
                    encoding="utf-8",
                )
            except subprocess.SubprocessError as e:
                LOG.debug(e)
    else:
        LOG.debug(
            "Install graphviz package and ensure the command `dot` is available in the PATH to convert to png automatically"
        )


def do_x_build(src, env, build_artefacts, tool_lang):
    """Method to guess and build applications"""
    tool_lang = tool_lang.split("-")[0]
    build_crashes = {}
    for k, v in build_artefacts.items():
        failed_modules = 0
        crashed_modules = 0
        build_sets = build_tools_map.get(tool_lang)
        if isinstance(build_sets, dict):
            build_args = build_tools_map[tool_lang][k]
        else:
            build_args = build_sets
        if len(v) > 5:
            LOG.debug(
                "This project has %d modules. Build might take a while ...", len(v)
            )
        for afile in v:
            base_dir = os.path.dirname(afile)
            build_args_str = " ".join(build_args)
            if "%(" in build_args_str:
                gradle_cmd = "gradle"
                maven_cmd = "mvn"
                if os.path.exists(os.path.join(base_dir, "gradlew")):
                    gradle_cmd = "gradlew"
                    try:
                        os.chmod(os.path.join(base_dir, "gradlew"), 0o755)
                    except OSError:
                        # Ignore errors
                        pass
                if os.path.exists(os.path.join(base_dir, "mvnw")):
                    maven_cmd = "mvnw"
                    try:
                        os.chmod(os.path.join(base_dir, "mvnw"), 0o755)
                    except OSError:
                        # Ignore errors
                        pass
                build_args_str = build_args_str % dict(
                    gradle_cmd=gradle_cmd, maven_cmd=maven_cmd
                )
            try:
                LOG.debug("Executing build command: %s in %s", build_args_str, base_dir)
                cp = subprocess.run(
                    build_args_str.split(" "),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=base_dir,
                    env=env,
                    check=False,
                    shell=USE_SHELL,
                    encoding="utf-8",
                )
                if cp:
                    # These languages always need troubleshooting
                    if tool_lang in ("csharp", "dotnet", "go"):
                        if cp.stderr:
                            LOG.info(cp.stderr)
                        if cp.stdout:
                            LOG.info(cp.stdout)
                    elif LOG.isEnabledFor(DEBUG) and cp.returncode and cp.stderr:
                        LOG.debug(cp.stderr)
                    failed_modules = failed_modules + 1
            except subprocess.SubprocessError:
                LOG.info(exc_info=True)
                crashed_modules = crashed_modules + 1
        build_crashes[k] = {
            "failed_modules": failed_modules,
            "crashed_modules": crashed_modules,
        }
    return build_crashes


def do_jar_build(tool_lang, src, env):
    """Method to build java apps"""
    build_artefacts = {
        "gradle": find_gradle_files(src),
        "maven": find_pom_files(src),
        "sbt": find_sbt_files(src),
    }
    settings_xmls = find_files(src, "settings.xml", False, False)
    if settings_xmls:
        LOG.info(
            "Maven settings.xml is present in this repo. This usually means that specific maven settings and profiles needs to be passed via the environment variable MVN_ARGS to build this application correctly."
        )
        if not os.getenv("AT_DEBUG_MODE"):
            LOG.info(
                "Set the environment variable AT_DEBUG_MODE to debug and look for any build errors"
            )
    return do_x_build(src, env, build_artefacts, tool_lang)


def do_go_build(src, env):
    """Method to build go apps"""
    build_artefacts = {
        "mage": find_files(src, "magefile.go", False, False),
        "go": find_go_mods(src),
        "make": find_makefiles(src),
    }
    return do_x_build(src, env, build_artefacts, "go")


def do_build(tool_lang, src, cwd, env):
    """Method to build various apps"""
    if tool_lang in ("csharp",):
        if os.path.exists(os.path.join(src, "global.json")):
            LOG.debug(
                "global.json is found in the root directory. Ensure the correct version of dotnet sdk is installed.\nAlternatively, set the rollForward property to latestMajor to use the bundled .Net 7 SDK from the cpggen container image."
            )
        return do_x_build(src, env, {"csharp": find_csharp_artifacts(src)}, "csharp")
    elif (
        tool_lang in ("jar", "scala")
        or tool_lang.startswith("jar")
        or tool_lang.startswith("jsp")
    ):
        return do_jar_build(tool_lang, src, env)
    elif tool_lang == "go":
        return do_go_build(src, env)


def troubleshoot_app(lang_build_crashes, tool_lang):
    """Not implemented yet"""
    pass


def exec_tool(
    tool_lang,
    src,
    cpg_out_dir,
    cwd=None,
    joern_home=None,
    use_container=False,
    use_atom=False,
    auto_build=False,
    extra_args=None,
    env=None,
    stdout=subprocess.DEVNULL,
):
    """Method to execute tools to generate cpg or perform exports"""
    if env is None:
        env = os.environ.copy()
    cpggen_memory = os.getenv("CPGGEN_MEMORY", max_memory)
    env[
        "JAVA_OPTS"
    ] = f'{os.getenv("JAVA_OPTS", "")} -Xms{cpggen_memory} -Xmx{cpggen_memory}'
    if extra_args is None:
        extra_args = {}
    with Progress(
        console=console,
        transient=True,
        redirect_stderr=False,
        redirect_stdout=False,
        refresh_per_second=1,
    ) as progress:
        task = None
        lang_build_crashes = {}
        app_manifest_list = []
        tool_lang_simple = tool_lang.split("-")[0]
        atom_home = os.getenv("ATOM_HOME")
        atom_bin_dir = os.getenv("ATOM_BIN_DIR")
        whats_built = "CPG"
        if not atom_bin_dir:
            if atom_home:
                atom_bin_dir = os.path.join(atom_home, "bin", "")
            else:
                # Handle the case where the user might have installed atom npm package on windows
                # but not set the PATH environment variable
                atom_bin_dir = (
                    str(Path.home() / "AppData" / "Roaming" / "npm")
                    if sys.platform == "win32"
                    else "/usr/local/bin"
                )
                atom_bin_dir = os.path.join(atom_bin_dir, "")
                if sys.platform == "win32" and os.path.exists(atom_bin_dir):
                    os.environ["ATOM_BIN_DIR"] = os.path.join(atom_bin_dir)
                    os.environ["PATH"] = (
                        os.environ["PATH"] + os.pathsep + atom_bin_dir + os.pathsep
                    )
        # Set joern_home from environment variable
        # This is required to handle bundled exe mode
        if (
            not joern_home
            and os.getenv("JOERN_HOME")
            and os.path.exists(os.getenv("JOERN_HOME"))
        ):
            joern_home = os.getenv("JOERN_HOME")
        if cwd:
            if os.path.isfile(cwd):
                cwd = os.path.dirname(cwd)
            else:
                cwd = os.path.abspath(cwd)
        if joern_home and not joern_home.endswith(os.path.sep):
            joern_home = f"{joern_home}{os.path.sep}"
        if atom_home and not atom_home.endswith(os.path.sep):
            atom_home = f"{atom_home}{os.path.sep}"
            # Use atom for supported languages if available
            if tool_lang_simple in (
                "java",
                "c",
                "cpp",
                "js",
                "jimple",
                "ts",
                "python",
                "javascript",
                "typescript",
            ):
                use_atom = True
                whats_built = "atom"
        try:
            stderr = subprocess.DEVNULL
            if LOG.isEnabledFor(DEBUG):
                stdout = subprocess.PIPE
                stderr = stdout
            tool_verb = f"Building {whats_built} with {tool_lang} frontend"
            if tool_lang == "export":
                tool_verb = "Exporting CPG with joern-export"
            elif tool_lang == "slice":
                tool_verb = "Slicing CPG with joern-slice"
            elif tool_lang == "vectors":
                tool_verb = "Generating CPG vectors with joern-vectors"
            task = progress.add_task(
                "[green]" + tool_verb,
                total=100,
                start=False,
            )
            cpg_cmd_lang = tool_lang
            # If the intention is to export or slice then use joern-parse
            if use_atom or (
                extra_args
                and (extra_args.get("for_export") or extra_args.get("for_slice"))
            ):
                cpg_cmd_lang = ATOM_CMD if check_command(ATOM_CMD) else "parse"
            cmd_with_args = cpg_tools_map.get(cpg_cmd_lang)
            if not cmd_with_args:
                return
            # Perform build first
            if build_tools_map.get(tool_lang):
                if os.getenv("CI"):
                    LOG.debug(
                        "Automatically building %s for %s. To speed up this step, cache the build dependencies using the CI cache settings.",
                        src,
                        tool_lang,
                    )
                elif use_container:
                    LOG.debug(
                        "Attempting to build %s for %s using the bundled build tools from the container image.",
                        src,
                        tool_lang,
                    )
                else:
                    LOG.debug(
                        "Attempting to build %s for %s using the locally available build tools.\nFor better results, please ensure the correct version of these tools are installed for your application.\nAlternatively, use container image based execution.",
                        src,
                        tool_lang,
                    )
                lang_build_crashes[tool_lang] = do_build(tool_lang, src, cwd, env)
            uber_jar = ""
            csharp_artifacts = ""
            # For languages like scala, jsp or jar we need to create a uber jar containing all jar, war files from the source directory
            if "uber_jar" in cmd_with_args:
                stdout = subprocess.PIPE
                java_artifacts = find_java_artifacts(src)
                if len(java_artifacts) > 0:
                    uber_jar = java_artifacts[0]
            if "csharp_artifacts" in cmd_with_args:
                stdout = subprocess.PIPE
                csharp_artifacts = find_csharp_artifacts(src)
                if len(csharp_artifacts):
                    csharp_artifacts = csharp_artifacts[0]
            modules = [src]
            # For go, the modules are based on the presence of go.mod files
            if tool_lang == "go":
                go_mods = find_go_mods(src)
                if go_mods:
                    modules = [os.path.dirname(gmod) for gmod in go_mods]
            for amodule in modules:
                # Expand . directory names
                if amodule == ".":
                    amodule = os.path.abspath(amodule)
                cmd_with_args = cpg_tools_map.get(cpg_cmd_lang)
                # Fallback to atom if the command doesn't exist
                if (
                    not use_atom
                    and not check_command(cmd_with_args.split(" ")[0])
                    and check_command(ATOM_CMD)
                ):
                    cmd_with_args = cpg_tools_map.get("atom")
                    use_atom = True
                    whats_built = "atom"
                elif use_container:
                    # We need to make src an absolute path since relative paths wouldn't work in container mode
                    amodule = os.path.abspath(amodule)
                    container_cli = "docker"
                    if check_command("podman"):
                        container_cli = "podman"
                    cmd_with_args = f"""{container_cli} run --rm -w {amodule} -v {tempfile.gettempdir()}:/tmp -v {amodule}:{amodule}:rw -v {os.path.abspath(cpg_out_dir)}:{os.path.abspath(cpg_out_dir)}:rw -t {os.getenv("CPGGEN_IMAGE", "ghcr.io/appthreat/cpggen")} {cmd_with_args}"""
                    # We need to fix joern_home to the directory inside the container
                    joern_home = ""
                sbom_cmd_with_args = cpg_tools_map.get("sbom")
                sbom_out = ""
                manifest_out = ""
                slice_out = extra_args.get("slice_out", "")
                cpg_out = (
                    cpg_out_dir
                    if cpg_out_dir.endswith(".cpg.bin")
                    or cpg_out_dir.endswith(".cpg.bin.zip")
                    or cpg_out_dir.endswith(".bin")
                    or cpg_out_dir.endswith(".cpg")
                    or cpg_out_dir.endswith(".⚛")
                    or cpg_out_dir.endswith(".atom")
                    else os.path.abspath(
                        os.path.join(
                            cpg_out_dir,
                            f"{os.path.basename(amodule)}-{tool_lang_simple}.cpg.bin",
                        )
                    )
                )
                atom_out = (
                    cpg_out.replace(".cpg.bin.zip", ".cpg.bin").replace(
                        ".cpg.bin", f".{'⚛' if sys.platform != 'win32' else 'atom'}"
                    )
                    if cpg_out.endswith(".cpg.bin")
                    else cpg_out
                    if cpg_out.endswith(".⚛") or cpg_out.endswith(".atom")
                    else f"{cpg_out}.{'⚛' if sys.platform != 'win32' else 'atom'}"
                )
                # BUG: go2cpg only works if the file extension is .cpg.bin.zip
                if tool_lang_simple == "go" and not cpg_out.endswith(".cpg.bin.zip"):
                    cpg_out = cpg_out.replace(".cpg.bin", ".cpg.bin.zip")
                if tool_lang in ("export", "vectors"):
                    cpg_out = os.path.abspath(cpg_out_dir)
                elif tool_lang == "slice":
                    cpg_out = src
                else:
                    sbom_out = (
                        cpg_out.replace(".cpg.bin.zip", ".cpg.bin").replace(
                            ".cpg.bin", ".bom.xml"
                        )
                        if cpg_out.endswith(".cpg.bin")
                        else f"{cpg_out}.bom.xml"
                    )
                    manifest_out = (
                        cpg_out.replace(".cpg.bin.zip", ".cpg.bin").replace(
                            ".cpg.bin", ".manifest.json"
                        )
                        if cpg_out.endswith(".cpg.bin")
                        else f"{cpg_out}.manifest.json"
                    )
                    LOG.debug("%s file for %s is %s", whats_built, tool_lang, cpg_out)
                if not slice_out:
                    slice_out = cpg_out.replace(".cpg.bin.zip", ".cpg.bin").replace(
                        ".cpg.bin", ".slices.json"
                    )
                    extra_args["slice_out"] = slice_out
                cmd_with_args = cmd_with_args % dict(
                    src=os.path.abspath(amodule),
                    cpg_out=cpg_out,
                    atom_out=atom_out,
                    atom_bin_dir=atom_bin_dir,
                    joern_home=joern_home,
                    home_dir=str(Path.home()),
                    uber_jar=uber_jar,
                    csharp_artifacts=csharp_artifacts,
                    memory=cpggen_memory,
                    tool_lang=tool_lang,
                    parse_lang=joern_parse_lang_map.get(
                        tool_lang_simple, tool_lang_simple
                    ),
                    sbom_out=sbom_out,
                    cpggen_bin_dir=os.getenv("CPGGEN_BIN_DIR", "/usr/local/bin"),
                    bin_ext=bin_ext,
                    exe_ext=exe_ext,
                    only_bat_ext=only_bat_ext,
                    android_jar=f' {os.getenv("JIMPLE_ANDROID_JAR", "").strip()}'
                    if os.getenv("JIMPLE_ANDROID_JAR")
                    else "",
                    os_path_sep=os.path.sep,
                    **extra_args,
                )
                sbom_lang = tool_lang_simple
                if (
                    tool_lang in ("jar", "scala", "jimple")
                    or tool_lang.startswith("jar")
                    or tool_lang.startswith("jsp")
                ):
                    sbom_lang = "java"
                sbom_cmd_with_args = sbom_cmd_with_args % dict(
                    src=os.path.abspath(src),
                    tool_lang=sbom_lang,
                    cwd=cwd,
                    atom_out=atom_out,
                    sbom_out=sbom_out,
                    cdxgen_cmd=cdxgen_cmd,
                    bin_ext=bin_ext,
                    exe_ext=exe_ext,
                    only_bat_ext=only_bat_ext,
                    os_path_sep=os.path.sep,
                    cdxgen_args=f' {os.getenv("CDXGEN_ARGS", "").strip()}'
                    if os.getenv("CDXGEN_ARGS")
                    else "",
                    atom_bin_dir=atom_bin_dir,
                    cpggen_bin_dir=os.getenv("CPGGEN_BIN_DIR", "/usr/local/bin"),
                    **extra_args,
                )
                cmd_list_with_args = cmd_with_args.split(" ")
                sbom_cmd_list_with_args = sbom_cmd_with_args.split(" ")
                lang_cmd = cmd_list_with_args[0]
                if not check_command(lang_cmd) and not os.path.exists(lang_cmd):
                    if not use_container:
                        LOG.warning(
                            "%s is not found. Try running cpggen with --use-container argument.",
                            lang_cmd,
                        )
                    elif not use_atom:
                        LOG.warning(
                            "Try running cpggen with --use-atom argument to use AppThreat atom command."
                        )
                    else:
                        LOG.warning(
                            "%s is not found. Ensure the PATH variable in your container image is set to the bin directory of Joern.",
                            lang_cmd,
                        )
                    return
                # Is this an Export or Slice task?
                if tool_lang in ("export", "slice", "vectors"):
                    try:
                        progress.update(
                            task,
                            description=f"{tool_lang.capitalize()} CPG",
                            completed=90,
                            total=100,
                        )
                        cp = subprocess.run(
                            cmd_list_with_args,
                            stdout=stdout,
                            stderr=stderr,
                            cwd=cwd,
                            env=env,
                            check=False,
                            shell=USE_SHELL,
                            encoding="utf-8",
                        )
                        # Bug. joern-vectors doesn't create json
                        if tool_lang == "vectors" and cp and cp.stdout:
                            os.makedirs(cpg_out_dir, exist_ok=True)
                            with open(
                                os.path.join(cpg_out_dir, "vectors.json"),
                                mode="w",
                                encoding="utf-8",
                            ) as fp:
                                fp.write(cp.stdout)
                        if cp and cp.returncode and cp.stderr:
                            LOG.warning(
                                "%s operation has failed for %s",
                                tool_lang.capitalize(),
                                src,
                            )
                            if not os.getenv("AT_DEBUG_MODE"):
                                LOG.info(
                                    "Set the environment variable AT_DEBUG_MODE to debug to see the debug logs"
                                )
                            if cp.stdout:
                                LOG.info(cp.stdout)
                            if cp.stderr:
                                LOG.info("------------------------------")
                                LOG.info(cp.stderr)
                                LOG.info("------------------------------")
                                LOG.info(
                                    "Command used %s\nPlease report the above error to https://github.com/appthreat/joern/issues",
                                    " ".join(cmd_list_with_args),
                                )
                        else:
                            check_dir = (
                                cpg_out_dir
                                if tool_lang == "export"
                                else (
                                    os.path.join(cpg_out_dir, "vectors.json")
                                    if tool_lang == "vectors"
                                    else slice_out
                                )
                            )
                            if os.path.exists(check_dir):
                                if tool_lang == "vectors":
                                    LOG.info(
                                        "CPG %s successfully vectorized to %s",
                                        src,
                                        check_dir,
                                    )
                                else:
                                    LOG.info(
                                        "CPG %s successfully %s to {check_dir}",
                                        src,
                                        tool_lang
                                        + ("d" if tool_lang.endswith("e") else "ed"),
                                    )
                                # Convert dot files to png
                                if tool_lang == "export":
                                    progress.update(
                                        task,
                                        description="Convert exported graph to png",
                                        completed=95,
                                        total=100,
                                    )
                                    dot_convert(cpg_out_dir, env)
                            else:
                                LOG.warning(
                                    "Unable to %s %s to %s. Try running joern-%s manually using the command %s",
                                    tool_lang,
                                    src,
                                    check_dir,
                                    tool_lang,
                                    " ".join(cmd_list_with_args),
                                )
                    except subprocess.SubprocessError:
                        LOG.warning(
                            "Unable to %s %s to %s",
                            tool_lang,
                            src,
                            cpg_out_dir,
                            exc_info=True,
                        )
                    progress.update(task, completed=100, total=100)
                    continue
                LOG.debug(
                    '⚡︎ Generating %s for the %s app "%s" - "%s"',
                    whats_built,
                    tool_lang,
                    os.path.basename(amodule),
                    " ".join(cmd_list_with_args),
                )
                cwd = amodule
                if tool_lang in ("binary",):
                    cwd = os.getcwd()
                if tool_lang != "binary" and not extra_args.get("skip_sbom"):
                    # Generate sbom first since this would even download dependencies for java
                    try:
                        progress.update(
                            task,
                            description="Generating SBoM using cdxgen",
                            completed=10,
                            total=100,
                        )
                        # Enable debug for sbom tool
                        if LOG.isEnabledFor(DEBUG):
                            env["CDXGEN_DEBUG_MODE"] = "debug"
                        LOG.debug("Executing %s", " ".join(sbom_cmd_list_with_args))

                        cp = subprocess.run(
                            sbom_cmd_list_with_args,
                            stdout=stdout,
                            stderr=stderr,
                            cwd=cwd,
                            env=env,
                            check=False,
                            shell=USE_SHELL,
                            encoding="utf-8",
                        )
                        if cp and LOG.isEnabledFor(DEBUG):
                            if cp.stdout:
                                LOG.debug(cp.stdout)
                            if cp.stderr:
                                LOG.debug(cp.stderr)
                    except subprocess.SubprocessError:
                        # Ignore SBoM errors
                        pass
                progress.update(
                    task,
                    description=f"Generating {tool_lang_simple} {whats_built}",
                    completed=20,
                    total=100,
                )
                cp = subprocess.run(
                    cmd_list_with_args,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=cwd,
                    env=env,
                    check=False,
                    shell=USE_SHELL,
                    encoding="utf-8",
                )
                if cp and stdout == subprocess.PIPE:
                    for line in cp.stdout:
                        progress.update(task, completed=5)
                if cp and cp.returncode:
                    if cp.stdout:
                        LOG.info(cp.stdout)
                    if cp.stderr:
                        LOG.info(cp.stderr)
                # If the tool produced atom file then prefer that over cpg
                if not os.path.exists(cpg_out) and os.path.exists(atom_out):
                    cpg_out = atom_out
                if os.path.exists(cpg_out):
                    if os.getenv("CI"):
                        LOG.info(
                            """%s %s generated successfully for %s.""",
                            whats_built,
                            cpg_out,
                            tool_lang,
                        )
                    else:
                        LOG.info(
                            """%s for %s is %s.\nTo import this in joern, use importCpg(%r)""",
                            whats_built,
                            tool_lang_simple,
                            cpg_out,
                            str(PureWindowsPath(cpg_out))
                            if sys.platform == "win32"
                            else cpg_out,
                        )
                    with open(manifest_out, mode="w", encoding="utf-8") as mfp:
                        # In case of github action, we need to convert this to relative path
                        if os.getenv("GITHUB_PATH"):
                            cpg_out = cpg_out.replace("/github/workspace/", "")
                            sbom_out = sbom_out.replace("/github/workspace/", "")
                            amodule = amodule.replace("/github/workspace/", "")
                        language = tool_lang_simple
                        app_base_name = os.path.basename(amodule)
                        # Let's improve the name for github action
                        if app_base_name == "workspace" and os.getenv(
                            "GITHUB_REPOSITORY"
                        ):
                            app_base_name = os.getenv("GITHUB_REPOSITORY").split("/")[
                                -1
                            ]
                        full_app_name = extra_args.get(
                            "full_app_name", f"{app_base_name}-{language}"
                        )
                        if extra_args.get("url") and extra_args.get("url").startswith(
                            "pkg:"
                        ):
                            full_app_name = purl_to_friendly_name(extra_args.get("url"))
                        app_manifest = {
                            "src": amodule,
                            "group": app_base_name,
                            "app": full_app_name,
                            "cpg": cpg_out,
                            "sbom": sbom_out,
                            "slice_out": slice_out,
                            "language": language,
                            "tool_lang": tool_lang,
                            "cpg_frontend_invocation": " ".join(cmd_list_with_args),
                            "sbom_invocation": " ".join(sbom_cmd_list_with_args),
                        }
                        app_manifest_list.append(app_manifest)
                        json.dump(app_manifest, mfp)
                else:
                    LOG.debug("Command with args: %s", " ".join(cmd_list_with_args))
                    LOG.info(
                        "%s %s was not generated for %s. cwd: %s",
                        whats_built,
                        cpg_out,
                        tool_lang,
                        cwd,
                    )
                    if not os.getenv("AT_DEBUG_MODE"):
                        LOG.info(
                            "Set the environment variable AT_DEBUG_MODE to debug to see the debug logs"
                        )
                    if cp.stdout:
                        LOG.info(cp.stdout)
                    if cp.stderr:
                        LOG.info(cp.stderr)
                    troubleshoot_app(lang_build_crashes, tool_lang)
                progress.update(task, completed=100, total=100)
        except subprocess.SubprocessError as se:
            if not os.getenv("AT_DEBUG_MODE"):
                LOG.info(
                    "Set the environment variable AT_DEBUG_MODE to debug to see the debug logs"
                )
            LOG.warning(se)
    return app_manifest_list
