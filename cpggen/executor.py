import json
import os
import subprocess
import tempfile
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
    "c": "%(joern_home)sc2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "cpp": "%(joern_home)sc2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --with-include-auto-discovery",
    "java": "%(joern_home)sjavasrc2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --fetch-dependencies --inference-jar-paths %(home_dir)s/.m2",
    "binary": "%(joern_home)sghidra2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "js": "%(joern_home)sjssrc2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "ts": "%(joern_home)sjssrc2cpg.sh -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "kotlin": "%(joern_home)skotlin2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "kotlin-with-deps": "%(joern_home)skotlin2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --download-dependencies",
    "kotlin-with-classpath": "%(joern_home)skotlin2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s --classpath %(home_dir)s/.m2 --classpath %(home_dir)s/.gradle/caches/modules-2/files-2.1",
    "php": "%(joern_home)sphp2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "python": "%(joern_home)spysrc2cpg -J-Xmx%(memory)s -o %(cpg_out)s %(src)s",
    "csharp": "%(joern_home)scsharp2cpg -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-tests -l error",
    "dotnet": "%(joern_home)scsharp2cpg -i %(csharp_artifacts)s -o %(cpg_out)s --ignore-tests -l error",
    "go": "%(joern_home)sgo2cpg generate -o %(cpg_out)s ./...",
    "jar": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar /usr/local/bin/java2cpg.jar --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "jar-without-blocklist": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar /usr/local/bin/java2cpg.jar -nb --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "scala": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar /usr/local/bin/java2cpg.jar -nojsp --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "jsp": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar /usr/local/bin/java2cpg.jar --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "jsp-without-blocklist": "java -Xmx%(memory)s -Dorg.apache.el.parser.SKIP_IDENTIFIER_CHECK=true -jar /usr/local/bin/java2cpg.jar -nb --experimental-langs=scala -su -o %(cpg_out)s %(uber_jar)s",
    "sbom": "cdxgen -r -t %(tool_lang)s -o %(sbom_out)s %(src)s",
    "export": "joern-export --repr=%(export_repr)s --format=%(export_format)s --out %(cpg_out)s %(src)s",
    "qwiet": "sl analyze %(policy)s%(vcs_correction)s--tag app.group=%(group)s --app %(app)s --%(language)s --cpgupload --bomupload %(sbom)s %(cpg)s",
}

build_tools_map = {
    "csharp": ["dotnet", "build"],
    "java": {
        "maven": [
            get("MVN_CMD", "%(maven_cmd)s"),
            "compile",
        ],
        "gradle": [get("GRADLE_CMD", "%(gradle_cmd)s"), "build"],
        "sbt": ["sbt", "compile"],
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
    "nodejs": {
        "npm": ["npm", "install", "--prefer-offline", "--no-audit", "--progress=false"],
        "yarn": ["yarn", "install"],
        "rush": ["rush", "install", "--bypass-policy", "--no-link"],
    },
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


def qwiet_analysis(app_manifest, cwd, env):
    try:
        LOG.info(f"Submitting {app_manifest['app']} for Qwiet.AI analysis")
        build_args = cpg_tools_map["qwiet"]
        policy = ""
        vcs_correction = ""
        if os.getenv("SHIFTLEFT_POLICY"):
            policy = f"""--policy {os.getenv("SHIFTLEFT_POLICY")} """
        elif os.getenv("ENABLE_BEST_PRACTICES") in ("true", "1"):
            policy = f"""--policy io.shiftleft/defaultWithDictAndBestPractices """

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
            shell=False,
            encoding="utf-8",
        )
        if cp:
            if LOG.isEnabledFor(DEBUG) and cp.stdout:
                LOG.debug(cp.stdout)
            if cp.returncode and cp.stderr:
                LOG.info(cp.stderr)
            else:
                LOG.info(f"{app_manifest['app']} uploaded successfully")
    except Exception as e:
        LOG.error(e)


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
                f"This project has multiple modules. Build might take a while ..."
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
                LOG.debug(f"Executing {build_args_str} in {base_dir}")
                cp = subprocess.run(
                    build_args_str.split(" "),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=base_dir,
                    env=env,
                    check=False,
                    shell=False,
                    encoding="utf-8",
                )
                if cp and LOG.isEnabledFor(DEBUG) and cp.returncode and cp.stderr:
                    LOG.debug(cp.stderr)
                    failed_modules = failed_modules + 1
            except Exception as e:
                LOG.debug(e)
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
    print(lang_build_crashes, tool_lang)


def exec_tool(
    tool_lang,
    src,
    cpg_out_dir,
    cwd=None,
    joern_home=None,
    use_container=False,
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
        lang_build_crashes = None
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
            task = progress.add_task(
                "[green]" + tool_verb,
                total=100,
                start=False,
            )
            cmd_with_args = cpg_tools_map.get(tool_lang)
            if not cmd_with_args:
                return
            # Perform build first
            if auto_build:
                LOG.info(
                    f"Automatically building {src}. To speed up this step, cache the build dependencies using the CI cache settings."
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
                cmd_with_args = cpg_tools_map.get(tool_lang)
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
                if tool_lang == "export":
                    cpg_out = cpg_out_dir
                else:
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
                    **extra_args,
                )
                sbom_lang = tool_lang
                if (
                    tool_lang in ("jar", "scala")
                    or tool_lang.startswith("jar")
                    or tool_lang.startswith("jsp")
                ):
                    sbom_lang = "java"
                sbom_cmd_with_args = sbom_cmd_with_args % dict(
                    src=src, tool_lang=sbom_lang, sbom_out=sbom_out, **extra_args
                )
                cmd_list_with_args = cmd_with_args.split(" ")
                sbom_cmd_list_with_args = sbom_cmd_with_args.split(" ")
                lang_cmd = cmd_list_with_args[0]
                if not check_command(lang_cmd):
                    if not use_container:
                        LOG.warn(
                            f"{lang_cmd} is not found. Try running cpggen with --use-container argument"
                        )
                    else:
                        LOG.warn(
                            f"{lang_cmd} is not found. Ensure the PATH variable in your container image is set to the bin directory of Joern."
                        )
                    return
                # Is this an Export task?
                if tool_lang == "export":
                    try:
                        progress.update(
                            task, description="Exporting CPG", completed=90, total=100
                        )
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
                        if cp and cp.returncode and cp.stderr:
                            LOG.warn(f"Export CPG has failed for {src}")
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
                                    "Please report the above error to https://github.com/joernio/joern/issues"
                                )
                        else:
                            if os.path.exists(src):
                                LOG.info(
                                    f"CPG {src} successfully exported to {cpg_out_dir}"
                                )
                            else:
                                LOG.warn(
                                    f"Unable to export {src} to {cpg_out_dir}. Try running joern-export manually using the command {' '.join(cmd_list_with_args)}"
                                )
                    except Exception:
                        LOG.warn(f"Unable to export {src} to {cpg_out_dir}")
                    progress.update(task, completed=100, total=100)
                    continue
                LOG.info(
                    '⚡︎ Generating CPG for the {} app "{}" - "{}"'.format(
                        tool_lang,
                        os.path.basename(amodule),
                        " ".join(cmd_list_with_args),
                    )
                )
                cwd = amodule
                if tool_lang in ("binary",):
                    cwd = os.getcwd()
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
                        shell=False,
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
                    task, description="Generating CPG", completed=20, total=100
                )
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
                if cp and LOG.isEnabledFor(DEBUG) and cp.returncode:
                    if cp.stdout:
                        LOG.debug(cp.stdout)
                    if cp.stderr:
                        LOG.debug(cp.stderr)
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
                        language = tool_lang.split("-")[0]
                        # Override the language for jvm
                        if language in ("jar", "scala"):
                            language = "java"
                        app_base_name = os.path.basename(amodule)
                        # Let's improve the name for github action
                        if app_base_name == "workspace" and os.getenv(
                            "GITHUB_REPOSITORY"
                        ):
                            app_base_name = os.getenv("GITHUB_REPOSITORY").split("/")[
                                -1
                            ]
                        app_manifest = {
                            "src": amodule,
                            "group": app_base_name,
                            "app": f"{app_base_name}-{language}",
                            "cpg": cpg_out,
                            "sbom": sbom_out,
                            "language": language,
                            "tool_lang": tool_lang,
                            "cpg_frontend_invocation": " ".join(cmd_list_with_args),
                            "sbom_invocation": " ".join(sbom_cmd_list_with_args),
                        }
                        if os.getenv("SHIFTLEFT_ACCESS_TOKEN"):
                            progress.update(
                                task,
                                description="Uploading to Qwiet AI for analysis",
                                completed=90,
                                total=100,
                            )
                            qwiet_analysis(app_manifest, cwd, env)
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
            LOG.error(e)
