import io
import os
import subprocess

from rich.progress import Progress

from cpggen.logger import DEBUG, LOG, console
from cpggen.utils import check_command

cpg_tools_map = {
    "c": "c2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s",
    "cpp": "c2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s",
    "java": "javasrc2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "binary": "ghidra2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "js": "jssrc2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s",
    "ts": "jssrc2cpg.sh -J-Xmx32G -o %(cpg_out)s %(src)s",
    "kotlin": "kotlin2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "php": "php2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "python": "pysrc2cpg -J-Xmx32G -o %(cpg_out)s %(src)s",
    "csharp": "csharp2cpg -i %(src)s -o %(cpg_out)s --ignore-tests -l error",
    "dotnet": "csharp2cpg -i %(src)s -o %(cpg_out)s --ignore-tests -l error",
    "go": "go2cpg generate -o %(cpg_out)s ./...",
    "jar": "java -jar %(joern_home)s/java2cpg.jar -nojsp -nb --experimental-langs scala %(src)s %(cpg_out)s",
    "scala": "java -jar %(joern_home)s/java2cpg.jar -nojsp -nb --experimental-langs scala %(src)s %(cpg_out)s",
    "jsp": "java -jar %(joern_home)s/java2cpg.jar -nb --experimental-langs scala %(src)s %(cpg_out)s",
}


def exec_tool(
    tool_lang,
    src,
    cpg_out_dir,
    cwd=None,
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
                "[green]" + tool_verb + " " + tool_lang, total=100, start=False
            )
            cmd_with_args = cpg_tools_map.get(tool_lang)
            if not cmd_with_args:
                return None
            cpg_out = os.path.join(cpg_out_dir, f"{tool_lang}-cpg.bin.zip")
            cmd_with_args = cmd_with_args % dict(
                src=src, cpg_out=cpg_out, joern_home=os.getenv("JOERN_HOME")
            )
            cmd_with_args = cmd_with_args.split(" ")
            lang_cmd = cmd_with_args[0]
            if not check_command(lang_cmd):
                LOG.warn(
                    f"{lang_cmd} is not found. Try running cpggen using the container image ghcr.io/appthreat/cpggen"
                )
                return None
            LOG.debug('⚡︎ Executing {} "{}"'.format(tool_lang, " ".join(cmd_with_args)))
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
            return cp
        except Exception as e:
            if task:
                progress.update(task, completed=20, total=10, visible=False)
            LOG.error(e)
            return None
