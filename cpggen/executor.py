import io
import os
import subprocess

from cpggen.logger import LOG, DEBUG, console

from rich.progress import Progress

cpg_tools_map = {"java": ""}


def exec_tool(  # scan:ignore
    tool_name, args, cwd=None, env=os.environ.copy(), stdout=subprocess.DEVNULL
):
    """
    Convenience method to invoke cli tools
    Args:
      tool_name Tool name
      args cli command and args
      cwd Current working directory
      env Environment variables
      stdout stdout configuration for run command
    Returns:
      CompletedProcess instance
    """
    with Progress(
        console=console,
        transient=True,
        redirect_stderr=False,
        redirect_stdout=False,
        refresh_per_second=1,
    ) as progress:
        task = None
        try:
            LOG.debug('⚡︎ Executing {} "{}"'.format(tool_name, " ".join(args)))
            stderr = subprocess.DEVNULL
            if LOG.isEnabledFor(DEBUG):
                stderr = subprocess.STDOUT
            tool_verb = "Building CPG with"
            task = progress.add_task(
                "[green]" + tool_verb + " " + tool_name, total=100, start=False
            )
            cp = subprocess.run(
                args,
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
            LOG.debug(e)
            return None
