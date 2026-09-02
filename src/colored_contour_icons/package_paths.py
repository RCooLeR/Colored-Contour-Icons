"""Shared package ordering; deliberately independent of image/build libraries."""

import re
from pathlib import Path


def gui_package_sort_key(path: Path) -> tuple[int, str]:
    """Order split client packages numerically, including part10 and later."""
    match = re.fullmatch(r"gui-part(\d+)\.pkg", path.name)
    return (int(match.group(1)) if match else -1, path.name)
