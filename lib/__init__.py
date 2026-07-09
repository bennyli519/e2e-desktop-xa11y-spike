"""lib package: infrastructure (login flow, helpers) — not Page Objects."""
from lib.helpers import click_first_match
from lib.platform_utils import (
    IS_MAC,
    IS_WINDOWS,
    activate_app,
    launch_app,
    quit_app,
)

__all__ = [
    "click_first_match",
    "IS_MAC",
    "IS_WINDOWS",
    "activate_app",
    "launch_app",
    "quit_app",
]
