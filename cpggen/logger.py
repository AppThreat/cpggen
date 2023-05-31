import logging
import os

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Disable logging from 'httpx' module to reduce unnecessary output
for _ in ("httpx",):
    logging.getLogger(_).disabled = True

custom_theme = Theme({"info": "cyan", "warning": "purple4", "danger": "bold red"})
console = Console(
    log_time=False,
    log_path=False,
    theme=custom_theme,
    width=280,
    color_system="256",
    record=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console, markup=False, show_path=False, enable_link_path=False
        )
    ],
)
LOG = logging.getLogger(__name__)
USE_DEBUG = False

# Set logging level
if (
    USE_DEBUG
    or os.getenv("AT_DEBUG_MODE") in ("debug", "true", "1")
    or os.getenv("SHIFTLEFT_VERBOSE")
    or os.getenv("SHIFTLEFT_DIAGNOSTIC")
):
    LOG.setLevel(logging.DEBUG)

DEBUG = logging.DEBUG

# Function to enable debug mode
def enable_debug():
    LOG.setLevel(logging.DEBUG)
    os.environ["SHIFTLEFT_VERBOSE"] = "true"
    os.environ["SHIFTLEFT_DIAGNOSTIC"] = "true"
