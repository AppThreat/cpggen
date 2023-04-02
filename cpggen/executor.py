import os
import subprocess
from pathlib import Path

from rich.progress import Progress

from cpggen.logger import DEBUG, LOG, console
from cpggen.utils import check_command, find_java_artifacts, find_csharp_artifacts

import traceback

runtimeValues = {}


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
    "c": "%(joern_home)s/c2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "cpp": "%(joern_home)s/c2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "java": "%(joern_home)s/javasrc2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "java-with-deps": "%(joern_home)s/javasrc2cpg -J-Xmx32G -o %(cpg_out)s %(src)s --fetch-dependencies",
    "binary": "%(joern_home)s/ghidra2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "js": "%(joern_home)s/jssrc2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s",
    "ts": "%(joern_home)s/jssrc2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s",
    "kotlin": "%(joern_home)s/kotlin2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "kotlin-with-deps": "%(joern_home)s/kotlin2cpg -J-Xmx32G -o %(cpg_out)s %(src)s --download-dependencies",
    "kotlin-with-classpath": "%(joern_home)s/kotlin2cpg -J-Xmx32G -o %(cpg_out)s %(src)s --classpath %(home_dir)s/.m2 --classpath %(home_dir)s/.gradle/caches/modules-2/files-2.1",
    "php": "%(joern_home)s/php2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "python": "%(joern_home)s/pysrc2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "csharp": "%(joern_home)s/bin/csharp2cpg -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-tests -l error",
    "dotnet": "%(joern_home)s/bin/csharp2cpg -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-tests -l error",
    "go": "%(joern_home)s/go2cpg generate -o %(cpg_out)s ./...",
    "jar": "java -Xmx32G -jar %(joern_home)s/java2cpg.jar %(uber_jar)s -nojsp -nb --experimental-langs scala -su -o %(cpg_out)s",
    "scala": "java -Xmx32G -jar %(joern_home)s/java2cpg.jar %(uber_jar)s -nojsp -nb --experimental-langs scala -su -o %(cpg_out)s",
    "jsp": "java -Xmx32G -jar %(joern_home)s/java2cpg.jar %(uber_jar)s -nb --experimental-langs scala -su -o %(cpg_out)s",
}

build_tools_map = {
    "csharp": ["dotnet", "build"],
    "java": {
        "maven": [get("MVN_CMD"), "compile"],
        "gradle": [get("GRADLE_CMD"), "compileJava"],
        "sbt": ["sbt", "compile"],
    },
    "android": {"gradle": [get("GRADLE_CMD"), "compileDebugSources"]},
    "kotlin": {
        "maven": [get("MVN_CMD"), "compile"],
        "gradle": [get("GRADLE_CMD"), "build"],
    },
    "groovy": {
        "maven": [get("MVN_CMD"), "compile"],
        "gradle": [get("GRADLE_CMD"), "compileGroovy"],
    },
    "scala": {
        "maven": [get("MVN_CMD"), "compile"],
        "gradle": [get("GRADLE_CMD"), "compileScala"],
        "sbt": ["sbt", "compile"],
    },
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
}


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
                return None
            cpg_out = (
                cpg_out_dir
                if cpg_out_dir.endswith(".bin.zip")
                or cpg_out_dir.endswith(".bin")
                or cpg_out_dir.endswith(".cpg")
                else os.path.join(cpg_out_dir, f"{tool_lang}-cpg.bin.zip")
            )
            LOG.debug(f"CPG file for {tool_lang} can be found at {cpg_out}")
            if use_container:
                cmd_with_args = f"""docker run --rm -it -v /tmp:/tmp -v {src}:{src}:rw --cpus={os.cpu_count} --memory=16g -t {os.getenv("CPGGEN_IMAGE", "ghcr.io/appthreat/cpggen")} {cmd_with_args}"""
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
            cmd_with_args = cmd_with_args % dict(
                src=src,
                cpg_out=cpg_out,
                joern_home=joern_home,
                home_dir=str(Path.home()),
                uber_jar=uber_jar,
                csharp_artifacts=csharp_artifacts,
            )
            cmd_with_args = cmd_with_args.split(" ")
            lang_cmd = cmd_with_args[0]
            if not check_command(lang_cmd):
                LOG.warn(
                    f"{lang_cmd} is not found. Try running cpggen with --use-container argument"
                )
                return None
            LOG.info(
                '⚡︎ Generating CPG for {} "{}"'.format(
                    tool_lang, " ".join(cmd_with_args)
                )
            )
            if tool_lang in ("binary",):
                cwd = os.getcwd()
            cp = subprocess.run(
                cmd_with_args,
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
            progress.update(task, completed=100, total=100)
            if os.path.exists(cpg_out):
                LOG.info(
                    f"""CPG for {tool_lang} is {cpg_out}. You can import this in joern using importCpg("{cpg_out}")"""
                )
                return cp, cpg_out
            else:
                LOG.info(f"CPG was not generated successfully for {tool_lang}")
                LOG.error(cp.stdout)
            return cp, None
        except Exception as e:
            if task:
                progress.update(task, completed=20, total=10, visible=False)
            LOG.error(e)
            traceback.print_exc()
            return None
