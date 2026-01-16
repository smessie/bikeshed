# pylint: disable=wrong-import-position

from __future__ import annotations

import os
import platform
import subprocess
import sys


def verify_python_version() -> None:
    if sys.version_info < (3, 12):
        print(
            """Bikeshed now requires Python 3.12 or higher; you are on {}.
    For instructions on how to set up a pyenv with 3.12, see:
    https://speced.github.io/bikeshed/#installing""".format(
                platform.python_version(),
            ),
        )
        sys.exit(1)


verify_python_version()


from . import (
    config,
    update,
)
from .cli import main
from .Spec import Spec
