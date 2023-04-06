import json
import os
import subprocess
import tempfile
from pathlib import Path

import psutil
from psutil._common import bytes2human
from rich.markdown import Markdown
from rich.progress import Progress

from cpggen.logger import DEBUG, LOG, console
from cpggen.utils import (
    check_command,
    find_csharp_artifacts,
    find_go_mods,
    find_java_artifacts,
    find_makefiles,
)

runtimeValues = {}
svmem = psutil.virtual_memory()
max_memory = bytes2human(getattr(svmem, "available"), format="%(value).0f%(symbol)s")
cpu_count = str(psutil.cpu_count())


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
    "c": "%(joern_home)s/c2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "cpp": "%(joern_home)s/c2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "java": "%(joern_home)s/javasrc2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "java-with-deps": "%(joern_home)s/javasrc2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --fetch-dependencies",
    "binary": "%(joern_home)s/ghidra2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "js": "%(joern_home)s/jssrc2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "ts": "%(joern_home)s/jssrc2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "kotlin": "%(joern_home)s/kotlin2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "kotlin-with-deps": "%(joern_home)s/kotlin2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --download-dependencies",
    "kotlin-with-classpath": "%(joern_home)s/kotlin2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --classpath %(home_dir)s/.m2 --classpath %(home_dir)s/.gradle/caches/modules-2/files-2.1",
    "php": "%(joern_home)s/php2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "python": "%(joern_home)s/pysrc2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "csharp": "%(joern_home)s/bin/csharp2cpg -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-tests -l error",
    "dotnet": "%(joern_home)s/bin/csharp2cpg -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-tests -l error",
    "go": "%(joern_home)s/go2cpg generate -o %(cpg_out)s ./...",
    "jar": "java -Xmx%(memory)s -jar %(joern_home)s/java2cpg.jar %(uber_jar)s -nojsp -nb --experimental-langs scala -su -o %(cpg_out)s",
    "scala": "java -Xmx%(memory)s -jar %(joern_home)s/java2cpg.jar %(uber_jar)s -nojsp -nb --experimental-langs scala -su -o %(cpg_out)s",
    "jsp": "java -Xmx%(memory)s -jar %(joern_home)s/java2cpg.jar %(uber_jar)s -nb --experimental-langs scala -su -o %(cpg_out)s",
    "sbom": "cdxgen -t %(tool_lang)s -o %(sbom_out)s %(src)s",
}

build_tools_map = {
    "csharp": ["dotnet", "build"],
    "java": {
        "maven": [
            get("MVN_CMD", "mvn"),
            "compile",
            "package",
            "-Dmaven.test.skip=true",
        ],
        "gradle": [get("GRADLE_CMD", "gradle"), "build"],
        "sbt": ["sbt", "compile"],
    },
    "android": {"gradle": [get("GRADLE_CMD", "gradle"), "compileDebugSources"]},
    "kotlin": {
        "maven": [
            get("MVN_CMD", "mvn"),
            "compile",
            "package",
            "-Dmaven.test.skip=true",
        ],
        "gradle": [get("GRADLE_CMD", "gradle"), "build"],
    },
    "scala": ["sbt", "stage"],
    "nodejs": {
        "npm": ["npm", "install", "--prefer-offline", "--no-audit", "--progress=false"],
        "yarn": ["yarn", "install"],
        "rush": ["rush", "install", "--bypass-policy", "--no-link"],
    },
    "go": ["go", "build", "./..."],
    "php": {
        "init": ["composer", "init", "--quiet"],
        "install": ["composer", "install", "-n", "--ignore-platform-reqs"],
        "update": ["composer", "update", "-n", "--ignore-platform-reqs"],
        "autoload": ["composer", "dump-autoload", "-o"],
    },
    "make": ["make", "build"],
}


def do_go_build(src, env):
    go_mods = find_go_mods(src)
    makes = find_makefiles(src)
    build_args = build_tools_map["go"]
    for gmod in go_mods:
        base_dir = os.path.dirname(gmod)
        try:
            LOG.debug(f"Executing {' '.join(build_args)} in {base_dir}")
            cp = subprocess.run(
                build_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=base_dir,
                env=env,
                check=False,
                shell=False,
                encoding="utf-8",
            )
        except Exception as e:
            LOG.debug(e)
    build_args = build_tools_map["make"]
    for make in makes:
        base_dir = os.path.dirname(make)
        try:
            LOG.debug(f"Executing {' '.join(build_args)} in {base_dir}")
            cp = subprocess.run(
                build_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=base_dir,
                env=env,
                check=False,
                shell=False,
                encoding="utf-8",
            )
        except Exception as e:
            LOG.debug(e)


def do_build(tool_lang, src, cwd, env):
    build_args = None
    if tool_lang in ("csharp", "scala"):
        build_args = build_tools_map[tool_lang]
    elif tool_lang == "go":
        do_go_build(src, env)
    # For go, we need to detect the go.mod files and attempt build from those directories
    if build_args:
        LOG.info(
            '⚡︎ Attempting to auto build {} "{}"'.format(
                tool_lang, " ".join(build_args)
            )
        )
        try:
            cp = subprocess.run(
                build_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=cwd,
                env=env,
                check=False,
                shell=False,
                encoding="utf-8",
            )
            if cp:
                if cp.stdout:
                    LOG.info(cp.stdout)
                if cp.stderr:
                    LOG.info(cp.stderr)
        except Exception as e:
            LOG.warn("Auto build has failed")
            LOG.warn(e)


def exec_tool(
    tool_lang,
    src,
    cpg_out_dir,
    cwd=None,
    joern_home=None,
    use_container=False,
    auto_build=False,
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
        try:
            stderr = subprocess.DEVNULL
            if LOG.isEnabledFor(DEBUG):
                stderr = subprocess.STDOUT
            tool_verb = "Building CPG with"
            task = progress.add_task(
                "[green]" + tool_verb + " " + tool_lang + " frontend",
                total=100,
                start=False,
            )
            cmd_with_args = cpg_tools_map.get(tool_lang)
            if not cmd_with_args:
                return
            if use_container:
                # We need to make src an absolute path since relative paths wouldn't work in container mode
                src = os.path.abspath(src)
                container_cli = "docker"
                if check_command("podman"):
                    container_cli = "podman"
                # cmd_with_args = f"""{container_cli} run --rm -w {os.path.abspath(src)} -v /tmp:/tmp -v {os.path.abspath(src)}:{os.path.abspath(src)}:rw -v {os.path.abspath(cpg_out_dir)}:{os.path.abspath(cpg_out_dir)}:rw --cpus={os.getenv("CPGGEN_CONTAINER_CPU", cpu_count)} --memory={os.getenv("CPGGEN_CONTAINER_MEMORY", max_memory)} -t {os.getenv("CPGGEN_IMAGE", "ghcr.io/appthreat/cpggen")} {cmd_with_args}"""
                cmd_with_args = f"""{container_cli} run --rm -w {src} -v {tempfile.gettempdir()}:/tmp -v {src}:{src}:rw -v {os.path.abspath(cpg_out_dir)}:{os.path.abspath(cpg_out_dir)}:rw -t {os.getenv("CPGGEN_IMAGE", "ghcr.io/appthreat/cpggen")} {cmd_with_args}"""
                # We need to fix joern_home to the directory inside the container
                joern_home = "/opt/joern/joern-cli"
            uber_jar = ""
            csharp_artifacts = ""
            # For languages like scala, jsp or jar we need to create a uber jar containing all jar, war files from the source directory
            if "uber_jar" in cmd_with_args:
                stdout = subprocess.PIPE
                java_artifacts = find_java_artifacts(src)
                if len(java_artifacts) == 1:
                    uber_jar = java_artifacts[0]
            if "csharp_artifacts" in cmd_with_args:
                stdout = subprocess.PIPE
                csharp_artifacts = find_csharp_artifacts(src)
                if len(csharp_artifacts) == 1:
                    csharp_artifacts = csharp_artifacts[0]
            if auto_build:
                do_build(tool_lang, src, cwd, env)
            modules = [src]
            # For go, the modules are based on the presence of go.mod files
            if tool_lang == "go":
                go_mods = find_go_mods(src)
                if go_mods:
                    modules = [os.path.dirname(gmod) for gmod in go_mods]
            for amodule in modules:
                cmd_with_args = cpg_tools_map.get(tool_lang)
                sbom_cmd_with_args = cpg_tools_map.get("sbom")
                cpg_out = (
                    cpg_out_dir
                    if cpg_out_dir.endswith(".bin.zip")
                    or cpg_out_dir.endswith(".bin")
                    or cpg_out_dir.endswith(".cpg")
                    else os.path.join(
                        cpg_out_dir,
                        f"{os.path.basename(amodule)}-{tool_lang}-cpg.bin.zip",
                    )
                )
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
                cmd_with_args = cmd_with_args % dict(
                    src=amodule,
                    cpg_out=cpg_out,
                    joern_home=joern_home,
                    home_dir=str(Path.home()),
                    uber_jar=uber_jar,
                    csharp_artifacts=csharp_artifacts,
                    memory=os.getenv("CPGGEN_MEMORY", max_memory),
                    tool_lang=tool_lang,
                    sbom_out=sbom_out,
                )
                sbom_cmd_with_args = sbom_cmd_with_args % dict(
                    src=amodule,
                    tool_lang=tool_lang,
                    sbom_out=sbom_out,
                )
                cmd_list_with_args = cmd_with_args.split(" ")
                sbom_cmd_list_with_args = sbom_cmd_with_args.split(" ")
                lang_cmd = cmd_list_with_args[0]
                if not check_command(lang_cmd):
                    LOG.warn(
                        f"{lang_cmd} is not found. Try running cpggen with --use-container argument"
                    )
                    return
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
                cp = subprocess.run(
                    cmd_list_with_args,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=cwd,
                    env=env,
                    check=False,
                    shell=False,
                    encoding="utf-8",
                )
                if cp and stdout == subprocess.PIPE:
                    for line in cp.stdout:
                        progress.update(task, completed=5)
                if (
                    cp
                    and LOG.isEnabledFor(DEBUG)
                    and cp.returncode
                    and cp.stdout is not None
                ):
                    LOG.debug(cp.stdout)
                # Generate sbom
                try:
                    subprocess.run(
                        sbom_cmd_list_with_args,
                        stdout=stdout,
                        stderr=stderr,
                        cwd=cwd,
                        env=env,
                        check=False,
                        shell=False,
                        encoding="utf-8",
                    )
                except Exception:
                    # Ignore sbom generation errors
                    pass
                progress.update(task, completed=100, total=100)
                if os.path.exists(cpg_out):
                    LOG.info(
                        f"""CPG for {tool_lang} is {cpg_out}. You can import this in joern using importCpg("{cpg_out}")"""
                    )
                    with open(manifest_out, mode="w") as mfp:
                        json.dump(
                            {
                                "src": amodule,
                                "cpg": cpg_out,
                                "sbom": sbom_out,
                                "language": tool_lang,
                                "cpg_frontend_invocation": " ".join(cmd_list_with_args),
                                "sbom_invocation": " ".join(sbom_cmd_list_with_args),
                            },
                            mfp,
                        )
                else:
                    LOG.info(
                        f"CPG {cpg_out} was not generated successfully for {tool_lang}"
                    )
                    if cp.stdout:
                        LOG.info(cp.stdout)
                    if cp.stderr:
                        LOG.info(cp.stderr)
        except Exception as e:
            if task:
                progress.update(task, completed=20, total=10, visible=False)
            LOG.error(e)
