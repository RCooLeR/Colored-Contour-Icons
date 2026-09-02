"""Verify that a battleAtlas add-on was generated from the installed client."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from .package_paths import gui_package_sort_key


def _read_client_gui_resource(game_root: Path, resource: str) -> bytes:
    packages = game_root / "res" / "packages"
    for package in sorted(packages.glob("gui-part*.pkg"), key=gui_package_sort_key, reverse=True):
        with zipfile.ZipFile(package) as archive:
            try:
                return archive.read(resource)
            except KeyError:
                continue
    raise FileNotFoundError(resource)


def verify_addon(game_root: Path, package: Path) -> dict[str, str]:
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    compatibility = manifest["compatibility"]
    xml = _read_client_gui_resource(game_root, "gui/flash/atlases/battleAtlas.xml")
    dds = _read_client_gui_resource(game_root, "gui/flash/atlases/battleAtlas.dds")
    actual_xml = hashlib.sha256(xml).hexdigest()
    actual_dds = hashlib.sha256(dds).hexdigest()
    expected_xml = compatibility["sourceXmlSha256"]
    atlas = manifest["atlases"][0]
    expected_dds = atlas["sourceDdsSha256"]
    if actual_xml != expected_xml or actual_dds != expected_dds:
        raise ValueError(
            "battleAtlas add-on does not match the installed client; rebuild it "
            "(XML %s/%s, DDS %s/%s)"
            % (expected_xml, actual_xml, expected_dds, actual_dds)
        )
    return {"xmlSha256": actual_xml, "ddsSha256": actual_dds}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    arguments = parser.parse_args(argv)
    print(json.dumps(verify_addon(arguments.game_root, arguments.package), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
