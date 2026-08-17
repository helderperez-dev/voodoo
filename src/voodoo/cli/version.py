import platform

from voodoo import __version__
from voodoo.cli import terminal


def version():
    """
    Show Voodoo Framework version and environment info.
    """
    terminal.wordmark(__version__)
    terminal.blank()
    terminal.label_value(
        "python", f"{platform.python_version()} ({platform.python_implementation()})"
    )
    terminal.label_value("platform", platform.platform())
    terminal.blank()
