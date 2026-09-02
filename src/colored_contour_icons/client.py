"""Read current vehicle definitions and contour resources from a WoT client."""

from __future__ import annotations

import io
import os
import re
import zipfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree

from PIL import Image

from .bxml import loads as load_bxml
from .package_paths import gui_package_sort_key


VEHICLE_CLASSES = ("lightTank", "mediumTank", "heavyTank", "AT-SPG", "SPG")
LIST_PATTERN = re.compile(r"^scripts/item_defs/vehicles/([^/]+)/list\.xml$")
CONTOUR_PREFIX = "gui/maps/icons/vehicle/contour/"
CLASS_ALIASES = {
    # Mode-specific contours whose definitions are outside the regular nation lists.
    "germany-G1043_PzII_Luchs_StoryMode": "lightTank",
    "germany-G54_E-50_BR": "mediumTank",
}


@dataclass(frozen=True)
class Vehicle:
    resource_name: str
    nation: str
    identifier: str
    vehicle_class: str
    level: int | None


class ClientData:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.packages = self.root / "res" / "packages"
        if not self.packages.is_dir():
            raise FileNotFoundError("World of Tanks packages not found: %s" % self.packages)

    def client_version(self) -> str:
        # Preloaded clients may have no mods directory, and an installed client
        # may retain a newer/older test directory.  The client metadata is the
        # authoritative version whenever it contains a valid patch number.
        version_file = self.root / "version.xml"
        if version_file.is_file():
            try:
                version_text = ElementTree.parse(version_file).findtext("version", "")
                match = re.fullmatch(r"(?:v\.?)?(\d+(?:\.\d+){3})(?:\s+.*)?", version_text.strip())
                if match:
                    return match.group(1)
            except (ElementTree.ParseError, OSError):
                pass
        mods = self.root / "mods"
        versions = [
            path.name for path in mods.iterdir()
            if path.is_dir() and re.fullmatch(r"\d+(?:\.\d+){3}", path.name)
        ] if mods.is_dir() else []
        if not versions:
            raise FileNotFoundError("Could not detect the active client version")
        return max(versions, key=lambda value: tuple(map(int, value.split("."))))

    def vehicles(self) -> dict[str, Vehicle]:
        result: dict[str, Vehicle] = {}
        scripts_path = self.packages / "scripts.pkg"
        with zipfile.ZipFile(scripts_path) as package:
            for member in package.namelist():
                match = LIST_PATTERN.match(member)
                if not match:
                    continue
                nation = match.group(1)
                document = load_bxml(package.read(member))
                for identifier, data in document.items():
                    if not identifier or not isinstance(data, dict):
                        continue
                    tags_value = data.get("tags", "")
                    if isinstance(tags_value, dict):
                        tags_value = tags_value.get("", "")
                    tags = str(tags_value).split()
                    vehicle_class = next((tag for tag in VEHICLE_CLASSES if tag in tags), "")
                    if not vehicle_class:
                        continue
                    level_value = data.get("level")
                    try:
                        level = int(level_value)
                    except (TypeError, ValueError):
                        level = None
                    resource_name = "%s-%s" % (nation, identifier)
                    result[resource_name] = Vehicle(resource_name, nation, identifier, vehicle_class, level)
        return result

    def contours(self) -> Iterator[tuple[str, bytes, str]]:
        """Yield every current contour once; later GUI package parts win."""
        selected: dict[str, tuple[Path, str]] = {}
        package_paths = sorted(self.packages.glob("gui-part*.pkg"), key=gui_package_sort_key)
        # GUI archives contain thousands of entries. Reopening one for every
        # contour repeatedly reparses its central directory during generation.
        with ExitStack() as stack:
            packages = {}
            for package_path in package_paths:
                package = stack.enter_context(zipfile.ZipFile(package_path))
                packages[package_path] = package
                for member in package.namelist():
                    if not member.startswith(CONTOUR_PREFIX) or not member.lower().endswith(".png"):
                        continue
                    selected[Path(member).stem] = (package_path, member)
            for resource_name in sorted(selected):
                package_path, member = selected[resource_name]
                yield resource_name, packages[package_path].read(member), package_path.name

    def contour_image(self, resource_name: str) -> Image.Image:
        wanted = CONTOUR_PREFIX + resource_name + ".png"
        for package_path in sorted(self.packages.glob("gui-part*.pkg"), key=gui_package_sort_key, reverse=True):
            with zipfile.ZipFile(package_path) as package:
                try:
                    return Image.open(io.BytesIO(package.read(wanted))).convert("RGBA")
                except KeyError:
                    continue
        raise KeyError(resource_name)

    def read_gui_resource(self, resource_path: str) -> tuple[bytes, str]:
        """Read a GUI resource, preferring the highest numbered package part."""
        for package_path in sorted(self.packages.glob("gui-part*.pkg"), key=gui_package_sort_key, reverse=True):
            with zipfile.ZipFile(package_path) as package:
                try:
                    return package.read(resource_path), package_path.name
                except KeyError:
                    continue
        raise KeyError(resource_path)
