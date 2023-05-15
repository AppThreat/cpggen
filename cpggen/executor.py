import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

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
    to_friendly_name,
)

runtimeValues = {}
svmem = psutil.virtual_memory()
max_memory = bytes2human(getattr(svmem, "available"), format="%(value).0f%(symbol)s")
cpu_count = str(psutil.cpu_count())

only_bat_ext = ".bat" if sys.platform == "win32" else ""
bin_ext = ".bat" if sys.platform == "win32" else ".sh"
exe_ext = ".exe" if sys.platform == "win32" else ""
use_shell = True if sys.platform == "win32" else False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


# Check if we are running as a bundled executable and
# extract the binaries
cdxgen_cmd = os.environ.get("CDXGEN_CMD", "cdxgen")
local_bin_dir = resource_path("local_bin")
if os.path.exists(local_bin_dir):
    csharp2cpg_bundled = resource_path(
        os.path.join("local_bin", "joern-cli", "csharp2cpg.zip")
    )
    joern_bundled = resource_path(os.path.join("local_bin", "joern-cli.zip"))
    if os.path.exists(csharp2cpg_bundled) and not os.path.exists(
        os.path.join(local_bin_dir, "bin", "csharp2cpg")
    ):
        try:
            with zipfile.ZipFile(csharp2cpg_bundled, "r") as zip_ref:
                zip_ref.extractall(local_bin_dir)
                LOG.debug(f"Extracted {csharp2cpg_bundled}")
                if not os.path.exists(os.path.join(local_bin_dir, "bin", "csharp2cpg")):
                    LOG.debug("csharp2cpg could not be found after extraction")
        except Exception as e:
            LOG.info(
                "cpggen was prevented from extracting the csharp2cpg frontend.\nPlease check if your terminal has administrative privileges or if the antivirus is preventing this process.\nAlternatively, use container-based execution."
            )
            LOG.error(e)
    if os.path.exists(joern_bundled) and not os.path.exists(
        os.path.join(local_bin_dir, "joern-cli", "c2cpg.sh")
    ):
        try:
            with zipfile.ZipFile(joern_bundled, "r") as zip_ref:
                zip_ref.extractall(local_bin_dir)
                # Add execute permissions
                for dirname, subdirs, files in os.walk(local_bin_dir):
                    for filename in files:
                        if not filename.endswith(".jar") and (
                            filename.endswith("%(bin_ext)s")
                            or "2cpg" in filename
                            or "joern-" in filename
                        ):
                            os.chmod(os.path.join(dirname, filename), 0o755)
                LOG.debug(f"Extracted {joern_bundled}")
                os.environ["JOERN_HOME"] = os.path.join(local_bin_dir, "joern-cli")
                os.environ["CPGGEN_BIN_DIR"] = local_bin_dir
                os.environ["PATH"] += os.sep + os.environ["JOERN_HOME"] + os.sep
        except Exception as e:
            LOG.info(
                "cpggen was prevented from extracting the joern library.\nPlease check if your terminal has administrative privileges or if the antivirus is preventing this process.\nAlternatively, use container-based execution."
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


def get(configName, default_value=None):
    """Method to retrieve a config given a name. This method lazy loads configuration
    values and helps with overriding using a local config
    :param configName: Name of the config
    :return Config value
    """
    try:
        value = runtimeValues.get(configName)
        if value is None:
            value = os.environ.get(configName.replace("-", "_").upper())
        if value is None:
            value = default_value
        return value
    except Exception:
        return default_value


cpg_tools_map = {
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
    "csharp": "%(joern_home)sbin%(os_path_sep)scsharp2cpg%(exe_ext)s -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-errors --no-log-file --ignore-tests -l error",
    "dotnet": "%(joern_home)sbin%(os_path_sep)scsharp2cpg%(exe_ext)s -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-errors --no-log-file --ignore-tests -l error",
    "go": "%(joern_home)sgo2cpg%(exe_ext)s generate -o %(cpg_out)s ./...",
    "jar": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar %(cpggen_bin_dir)s/java2cpg.jar --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "jar-without-blocklist": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar %(cpggen_bin_dir)s/java2cpg.jar -nb --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "scala": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar %(cpggen_bin_dir)s/java2cpg.jar -nojsp --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "jsp": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar %(cpggen_bin_dir)s/java2cpg.jar --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "jsp-without-blocklist": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar %(cpggen_bin_dir)s/java2cpg.jar -nb --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "sbom": "%(cdxgen_cmd)s%(exe_ext)s%(cdxgen_args)s -r -t %(tool_lang)s -o %(sbom_out)s %(src)s",
    "parse": "%(joern_home)sjoern-parse%(only_bat_ext)s -J-Xmx%(memory)s --language %(parse_lang)s --output %(cpg_out)s %(src)s",
    "vectors": "%(joern_home)sjoern-vectors%(only_bat_ext)s -J-Xmx%(memory)s --out %(cpg_out)s %(src)s",
    "export": "%(joern_home)sjoern-export%(only_bat_ext)s -J-Xmx%(memory)s --repr=%(export_repr)s --format=%(export_format)s --out %(cpg_out)s %(src)s",
    "slice": "%(joern_home)sjoern-slice%(only_bat_ext)s -J-Xmx%(memory)s --dummy-types true --exclude-operators true -m %(slice_mode)s --out %(slice_out)s %(cpg_out)s",
    "qwiet": "sl%(exe_ext)s analyze %(policy)s%(vcs_correction)s--tag app.group=%(group)s --app %(app)s --%(language)s --cpgupload --bomupload %(sbom)s %(cpg)s",
    "dot2png": "dot -Tpng %(dot_file)s -o %(png_out)s",
}

cpg_tools_map["npm"] = cpg_tools_map["js"]
cpg_tools_map["ts"] = cpg_tools_map["js"]
cpg_tools_map["javascript"] = cpg_tools_map["js"]
cpg_tools_map["typescript"] = cpg_tools_map["js"]
cpg_tools_map["maven"] = cpg_tools_map["jimple"]
cpg_tools_map["pypi"] = cpg_tools_map["python"]
cpg_tools_map["nuget"] = cpg_tools_map["csharp"]
cpg_tools_map["golang"] = cpg_tools_map["go"]

build_tools_map = {
    "csharp": ["dotnet", "build"],
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

qwiet_lang_map = {
    "jar": "java",
    "jsp": "java",
    "scala": "java",
    "java": "javasrc",
    "python": "pythonsrc",
    "js": "js",
    "ts": "js",
    "javascript": "js",
    "typescript": "js",
    "go": "go",
    "csharp": "csharp",
    "dotnet": "csharp",
    "cpp": "c",
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
    "go": "golang",
    "csharp": "csharp",
    "dotnet": "csharp",
    "cpp": "newc",
    "c": "newc",
    "binary": "ghidra",
    "ruby": "rubysrc",
    "jimple": "java",
}


def qwiet_analysis(app_manifest, src, cwd, env):
    try:
        relative_path = os.path.relpath(cwd, src)
        if relative_path and not relative_path.startswith(".."):
            os.environ["SL_VCS_RELATIVE_PATH"] = relative_path
            env["SL_VCS_RELATIVE_PATH"] = relative_path
        LOG.info(f"Submitting {app_manifest['app']} for Qwiet.AI analysis")
        build_args = cpg_tools_map["qwiet"]
        policy = ""
        vcs_correction = ""
        if os.getenv("SHIFTLEFT_POLICY"):
            policy = f"""--policy {os.getenv("SHIFTLEFT_POLICY")} """
        elif os.getenv("ENABLE_BEST_PRACTICES") in ("true", "1"):
            policy = """--policy io.shiftleft/defaultWithDictAndBestPractices """

        if app_manifest.get("tool_lang"):
            if "jar" in app_manifest.get("tool_lang") or "jsp" in app_manifest.get(
                "tool_lang"
            ):
                vcs_correction = '--vcs-prefix-correction "*=src/main/java" '
            if "scala" in app_manifest.get("tool_lang"):
                vcs_correction = '--vcs-prefix-correction "*=src/main/scala" '
        build_args = build_args % dict(
            **app_manifest, policy=policy, vcs_correction=vcs_correction
        )
        LOG.debug(f"Executing {build_args}")
        cp = subprocess.run(
            build_args.split(" "),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            check=False,
            shell=use_shell,
            encoding="utf-8",
        )
        if cp:
            if cp.stdout:
                LOG.info(cp.stdout)
            if cp.returncode and cp.stderr:
                LOG.warn(cp.stderr)
            else:
                LOG.info(f"{app_manifest['app']} uploaded successfully")
    except Exception as e:
        LOG.error(e)


def dot_convert(export_out_dir, env):
    if check_command("dot"):
        dot_files = find_files(export_out_dir, ".dot", False, False)
        if len(dot_files) > 5:
            LOG.info(
                f"{len(dot_files)} dot files generated after export. Skipping dot2png conversion ..."
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
                    shell=use_shell,
                    encoding="utf-8",
                )
            except Exception as e:
                LOG.debug(e)
    else:
        LOG.debug(
            "Install graphviz package and ensure the command `dot` is available in the PATH to convert to png automatically"
        )


def do_x_build(src, env, build_artefacts, tool_lang):
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
                f"This project has {len(v)} modules. Build might take a while ..."
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
                    except Exception:
                        # Ignore errors
                        pass
                if os.path.exists(os.path.join(base_dir, "mvnw")):
                    maven_cmd = "mvnw"
                    try:
                        os.chmod(os.path.join(base_dir, "mvnw"), 0o755)
                    except Exception:
                        # Ignore errors
                        pass
                build_args_str = build_args_str % dict(
                    gradle_cmd=gradle_cmd, maven_cmd=maven_cmd
                )
            try:
                LOG.debug(f"Executing build command: {build_args_str} in {base_dir}")
                cp = subprocess.run(
                    build_args_str.split(" "),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=base_dir,
                    env=env,
                    check=False,
                    shell=use_shell,
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
            except Exception as e:
                LOG.info(e)
                crashed_modules = crashed_modules + 1
        build_crashes[k] = {
            "failed_modules": failed_modules,
            "crashed_modules": crashed_modules,
        }
    return build_crashes


def do_jar_build(tool_lang, src, env):
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
    build_artefacts = {
        "mage": find_files(src, "magefile.go", False, False),
        "go": find_go_mods(src),
        "make": find_makefiles(src),
    }
    return do_x_build(src, env, build_artefacts, "go")


def do_build(tool_lang, src, cwd, env):
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
    pass


def exec_tool(
    tool_lang,
    src,
    cpg_out_dir,
    cwd=None,
    joern_home=None,
    use_container=False,
    use_parse=False,
    auto_build=False,
    extra_args={},
    env=os.environ.copy(),
    stdout=subprocess.DEVNULL,
):
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
        try:
            stderr = subprocess.DEVNULL
            if LOG.isEnabledFor(DEBUG):
                stdout = subprocess.PIPE
                stderr = stdout
            tool_verb = f"Building CPG with {tool_lang} frontend"
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
            if use_parse or (
                extra_args
                and (extra_args.get("for_export") or extra_args.get("for_slice"))
            ):
                cpg_cmd_lang = "parse"
            cmd_with_args = cpg_tools_map.get(cpg_cmd_lang)
            if not cmd_with_args:
                return
            # Perform build first
            if build_tools_map.get(tool_lang):
                if os.getenv("CI"):
                    LOG.debug(
                        f"Automatically building {src} for {tool_lang}. To speed up this step, cache the build dependencies using the CI cache settings."
                    )
                elif use_container:
                    LOG.debug(
                        f"Attempting to build {src} for {tool_lang} using the bundled build tools from the container image."
                    )
                else:
                    LOG.debug(
                        f"Attempting to build {src} for {tool_lang} using the locally available build tools.\nFor better results, please ensure the correct version of these tools are installed for your application.\nAlternatively, use container image based execution."
                    )
                lang_build_crashes[tool_lang] = do_build(tool_lang, src, cwd, env)
            uber_jar = ""
            csharp_artifacts = ""
            # For languages like scala, jsp or jar we need to create a uber jar containing all jar, war files from the source directory
            if "uber_jar" in cmd_with_args:
                stdout = subprocess.PIPE
                java_artifacts = find_java_artifacts(src)
                if len(java_artifacts):
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
                cmd_with_args = cpg_tools_map.get(cpg_cmd_lang)
                if use_container:
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
                    if cpg_out_dir.endswith(".bin.zip")
                    or cpg_out_dir.endswith(".bin")
                    or cpg_out_dir.endswith(".cpg")
                    else os.path.abspath(
                        os.path.join(
                            cpg_out_dir,
                            f"{os.path.basename(amodule)}-{tool_lang_simple}-cpg.bin.zip",
                        )
                    )
                )
                if tool_lang in ("export", "vectors"):
                    cpg_out = os.path.abspath(cpg_out_dir)
                elif tool_lang == "slice":
                    cpg_out = src
                else:
                    sbom_out = (
                        cpg_out.replace(".bin.zip", ".bom.xml")
                        if cpg_out.endswith(".bin.zip")
                        else f"{cpg_out}.bom.xml"
                    )
                    manifest_out = (
                        cpg_out.replace(".bin.zip", ".manifest.json")
                        if cpg_out.endswith(".bin.zip")
                        else f"{cpg_out}.manifest.json"
                    )
                    LOG.debug(f"CPG file for {tool_lang} is {cpg_out}")
                if not slice_out:
                    slice_out = cpg_out.replace(".bin.zip", ".slices")
                    slice_out = slice_out + (
                        ".json" if extra_args.get("slice_mode") == "Usages" else ".cpg"
                    )
                    extra_args["slice_out"] = slice_out
                cmd_with_args = cmd_with_args % dict(
                    src=os.path.abspath(amodule),
                    cpg_out=cpg_out,
                    joern_home=joern_home,
                    home_dir=str(Path.home()),
                    uber_jar=uber_jar,
                    csharp_artifacts=csharp_artifacts,
                    memory=os.getenv("CPGGEN_MEMORY", max_memory),
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
                    tool_lang in ("jar", "scala")
                    or tool_lang.startswith("jar")
                    or tool_lang.startswith("jsp")
                ):
                    sbom_lang = "java"
                sbom_cmd_with_args = sbom_cmd_with_args % dict(
                    src=os.path.abspath(src),
                    tool_lang=sbom_lang,
                    cwd=cwd,
                    sbom_out=sbom_out,
                    cdxgen_cmd=cdxgen_cmd,
                    bin_ext=bin_ext,
                    exe_ext=exe_ext,
                    only_bat_ext=only_bat_ext,
                    os_path_sep=os.path.sep,
                    cdxgen_args=f' {os.getenv("CDXGEN_ARGS", "").strip()}'
                    if os.getenv("CDXGEN_ARGS")
                    else "",
                    cpggen_bin_dir=os.getenv("CPGGEN_BIN_DIR", "/usr/local/bin"),
                    **extra_args,
                )
                cmd_list_with_args = cmd_with_args.split(" ")
                sbom_cmd_list_with_args = sbom_cmd_with_args.split(" ")
                lang_cmd = cmd_list_with_args[0]
                if not check_command(lang_cmd) and not os.path.exists(lang_cmd):
                    if not use_container:
                        LOG.warn(
                            f"{lang_cmd} is not found. Try running cpggen with --use-container argument."
                        )
                    elif not use_parse:
                        LOG.warn(
                            "Try running cpggen with --use-parse argument to use joern-parse command instead of language frontends."
                        )
                    else:
                        LOG.warn(
                            f"{lang_cmd} is not found. Ensure the PATH variable in your container image is set to the bin directory of Joern."
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
                            shell=use_shell,
                            encoding="utf-8",
                        )
                        # Bug. joern-vectors doesn't create json
                        if tool_lang == "vectors" and cp and cp.stdout:
                            os.makedirs(cpg_out_dir, exist_ok=True)
                            with open(
                                os.path.join(cpg_out_dir, "vectors.json"), mode="w"
                            ) as fp:
                                fp.write(cp.stdout)
                        if cp and cp.returncode and cp.stderr:
                            LOG.warn(
                                f"{tool_lang.capitalize()} operation has failed for {src}"
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
                                    f"Command used {' '.join(cmd_list_with_args)}\nPlease report the above error to https://github.com/joernio/joern/issues"
                                )
                        else:
                            check_dir = (
                                cpg_out_dir
                                if tool_lang in ("export")
                                else (
                                    os.path.join(cpg_out_dir, "vectors.json")
                                    if tool_lang == "vectors"
                                    else slice_out
                                )
                            )
                            if os.path.exists(check_dir):
                                if tool_lang == "vectors":
                                    LOG.info(
                                        f"CPG {src} successfully vectorized to {check_dir}"
                                    )
                                else:
                                    LOG.info(
                                        f"CPG {src} successfully {tool_lang + ('d' if tool_lang.endswith('e') else 'ed')} to {check_dir}"
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
                                LOG.warn(
                                    f"Unable to {tool_lang} {src} to {check_dir}. Try running joern-{tool_lang} manually using the command {' '.join(cmd_list_with_args)}"
                                )
                    except Exception as e:
                        LOG.warn(f"Unable to {tool_lang} {src} to {cpg_out_dir}")
                        LOG.error(e)
                    progress.update(task, completed=100, total=100)
                    continue
                LOG.debug(
                    '⚡︎ Generating CPG for the {} app "{}" - "{}"'.format(
                        tool_lang,
                        os.path.basename(amodule),
                        " ".join(cmd_list_with_args),
                    )
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
                            env["SCAN_DEBUG_MODE"] = "debug"
                        LOG.debug(f"Executing {' '.join(sbom_cmd_list_with_args)}")

                        cp = subprocess.run(
                            sbom_cmd_list_with_args,
                            stdout=stdout,
                            stderr=stderr,
                            cwd=cwd,
                            env=env,
                            check=False,
                            shell=use_shell,
                            encoding="utf-8",
                        )
                        if cp and LOG.isEnabledFor(DEBUG):
                            if cp.stdout:
                                LOG.debug(cp.stdout)
                            if cp.stderr:
                                LOG.debug(cp.stderr)
                    except Exception:
                        # Ignore SBoM errors
                        pass
                progress.update(
                    task,
                    description=f"Generating {tool_lang_simple} CPG",
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
                    shell=use_shell,
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
                if os.path.exists(cpg_out):
                    # go2cpg seems to produce a cpg without read permissions
                    try:
                        os.chmod(cpg_out, 0o644)
                    except Exception:
                        # Ignore errors
                        pass
                    if os.getenv("CI"):
                        LOG.info(
                            f"""CPG {cpg_out} generated successfully for {tool_lang}."""
                        )
                    else:
                        LOG.info(
                            f"""CPG for {tool_lang} is {cpg_out}. You can import this in joern using importCpg("{cpg_out}")"""
                        )
                    with open(manifest_out, mode="w") as mfp:
                        # In case of github action, we need to convert this to relative path
                        if os.getenv("GITHUB_PATH"):
                            cpg_out = cpg_out.replace("/github/workspace/", "")
                            sbom_out = sbom_out.replace("/github/workspace/", "")
                            amodule = amodule.replace("/github/workspace/", "")
                        language = tool_lang_simple
                        # Override the language for jvm
                        if qwiet_lang_map.get(language):
                            language = qwiet_lang_map.get(language)
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
                            full_app_name = to_friendly_name(extra_args.get("url"))
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
                        if os.getenv("SHIFTLEFT_ACCESS_TOKEN"):
                            progress.update(
                                task,
                                description="Uploading to Qwiet AI for analysis",
                                completed=90,
                                total=100,
                            )
                            qwiet_analysis(app_manifest, src, cwd, env)
                        json.dump(app_manifest, mfp)
                else:
                    LOG.info(f"CPG {cpg_out} was not generated for {tool_lang}")
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
        except Exception as e:
            if not os.getenv("AT_DEBUG_MODE"):
                LOG.info(
                    "Set the environment variable AT_DEBUG_MODE to debug to see the debug logs"
                )
            print(e)
    return app_manifest_list
