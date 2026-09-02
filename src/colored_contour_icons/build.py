"""CLI builder for the coloured contour icon package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .client import CLASS_ALIASES, ClientData, VEHICLE_CLASSES
from .render import ramp_from_config, recolor_contour


PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _load_palette(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf", "arialbd.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _checker(width: int, height: int, cell: int = 8) -> Image.Image:
    image = Image.new("RGB", (width, height), "#181A1D")
    draw = ImageDraw.Draw(image)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill="#24272B")
    return image


def build_preview(client: ClientData, palette: dict, output: Path) -> None:
    examples = {
        "lightTank": ["ussr-R03_BT-7", "germany-G103_RU_251", "usa-A02_M2_lt"],
        "mediumTank": ["ussr-R04_T-34", "germany-G03_PzV_Panther", "usa-A05_M4_Sherman"],
        "heavyTank": ["ussr-R01_IS", "germany-G04_PzVI_Tiger_I", "usa-A09_T1_hvy"],
        "AT-SPG": ["ussr-R02_SU-85", "germany-G05_StuG_40_AusfG", "usa-A102_T28_concept"],
        "SPG": ["ussr-R15_S-51", "germany-G02_Hummel", "usa-A107_T1_HMC"],
    }
    scale = 3
    width, row_height = 1440, 116
    header_height = 92
    canvas = _checker(width, header_height + row_height * len(VEHICLE_CLASSES), 12)
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 13), "RCooLeR Colored Contour Icons — palette preview", font=_font(25, True), fill="#F2F2F2")
    draw.text((480, 58), "ORIGINAL", font=_font(16, True), fill="#A7ABB2")
    draw.text((965, 58), "COLOURED", font=_font(16, True), fill="#FFFFFF")

    for row, vehicle_class in enumerate(VEHICLE_CLASSES):
        y = header_height + row * row_height
        config = palette[vehicle_class]
        draw.rectangle((0, y, width, y + row_height - 1), fill="#111317" if row % 2 == 0 else "#17191D")
        draw.text((24, y + 22), config["label_uk"], font=_font(22, True), fill=config["highlight"])
        draw.text((24, y + 57), vehicle_class, font=_font(15), fill="#888E98")
        ramp = ramp_from_config(config)
        for column, resource_name in enumerate(examples[vehicle_class]):
            source = client.contour_image(resource_name)
            coloured = recolor_contour(source, ramp)
            for group_x, icon in ((355, source), (840, coloured)):
                resized = icon.resize((icon.width * scale, icon.height * scale), Image.Resampling.NEAREST)
                x = group_x + column * 155 + (145 - resized.width) // 2
                canvas.alpha_composite(resized, (x, y + 11)) if canvas.mode == "RGBA" else canvas.paste(resized, (x, y + 11), resized)
            short_name = resource_name.split("-", 1)[-1][:14]
            draw.text((355 + column * 155, y + 89), short_name, font=_font(11), fill="#AAB0B8")
            draw.text((840 + column * 155, y + 89), short_name, font=_font(11), fill="#E2E5E9")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)


def build_class_previews(contour_dir: Path, icons: dict[str, str], palette: dict, output_dir: Path) -> None:
    """Build zoomable class sheets containing every generated icon."""
    columns, cell_width, cell_height, scale = 12, 170, 68, 2
    output_dir.mkdir(parents=True, exist_ok=True)
    for vehicle_class in VEHICLE_CLASSES:
        names = sorted(name for name, category in icons.items() if category == vehicle_class)
        rows = math.ceil(len(names) / columns)
        width = columns * cell_width
        height = 74 + rows * cell_height
        canvas = _checker(width, height, 10)
        draw = ImageDraw.Draw(canvas)
        title = "%s — %s (%d)" % (palette[vehicle_class]["label_uk"], vehicle_class, len(names))
        draw.rectangle((0, 0, width, 73), fill="#111317")
        draw.text((24, 18), title, font=_font(26, True), fill=palette[vehicle_class]["highlight"])
        for index, resource_name in enumerate(names):
            column, row = index % columns, index // columns
            x, y = column * cell_width, 74 + row * cell_height
            if (column + row) % 2:
                draw.rectangle((x, y, x + cell_width - 1, y + cell_height - 1), fill="#15181C")
            icon = Image.open(contour_dir / (resource_name + ".png")).convert("RGBA")
            icon = icon.resize((icon.width * scale, icon.height * scale), Image.Resampling.NEAREST)
            canvas.paste(icon, (x + (cell_width - icon.width) // 2, y + 1), icon)
            label = resource_name.split("-", 1)[-1]
            if len(label) > 23:
                label = label[:22] + "…"
            draw.text((x + 5, y + 50), label, font=_font(10), fill="#C8CDD4")
        canvas.save(output_dir / (vehicle_class.replace("-", "_") + ".png"), optimize=True)


def _atlas_entries(xml_data: bytes) -> dict[str, tuple[int, int, int, int]]:
    root = ElementTree.fromstring(xml_data)
    entries: dict[str, tuple[int, int, int, int]] = {}
    for element in root.findall(".//SubTexture"):
        values = {child.tag: (child.text or "").strip() for child in element}
        entries[values["name"]] = tuple(int(values[key]) for key in ("x", "y", "width", "height"))
    return entries


def _dds_payload_info(data: bytes) -> tuple[int, int, int, int]:
    import struct
    if data[:4] != b"DDS ":
        raise ValueError("Not a DDS file")
    height, width = struct.unpack_from("<II", data, 12)
    four_cc = data[84:88]
    if four_cc != b"DXT5":
        raise ValueError("Expected DXT5 atlas, got %r" % four_cc)
    offset = 128
    expected = offset + math.ceil(width / 4) * math.ceil(height / 4) * 16
    if len(data) != expected:
        raise ValueError("Unexpected DDS payload size: %d, expected %d" % (len(data), expected))
    return width, height, offset, 16


def build_atlas(client: ClientData, atlas_name: str, contour_dir: Path, icons: dict[str, str], target_dir: Path) -> dict:
    """Patch only DXT5 blocks touched by contours, preserving all other blocks byte-for-byte."""
    xml_path = "gui/flash/atlases/%s.xml" % atlas_name
    dds_path = "gui/flash/atlases/%s.dds" % atlas_name
    xml_data, xml_package = client.read_gui_resource(xml_path)
    dds_data, dds_package = client.read_gui_resource(dds_path)
    entries = _atlas_entries(xml_data)
    width, height, payload_offset, block_size = _dds_payload_info(dds_data)
    source_image = Image.open(io.BytesIO(dds_data)).convert("RGBA")
    modified = source_image.copy()
    touched: set[tuple[int, int]] = set()
    replaced = 0
    dimension_errors: list[str] = []
    for resource_name in sorted(icons):
        rect = entries.get(resource_name)
        if rect is None:
            continue
        x, y, icon_width, icon_height = rect
        icon = Image.open(contour_dir / (resource_name + ".png")).convert("RGBA")
        if icon.size != (icon_width, icon_height):
            dimension_errors.append("%s: %s != %s" % (resource_name, icon.size, (icon_width, icon_height)))
            continue
        modified.paste(icon, (x, y))
        for block_y in range(y // 4, math.ceil((y + icon_height) / 4)):
            for block_x in range(x // 4, math.ceil((x + icon_width) / 4)):
                touched.add((block_x, block_y))
        replaced += 1
    if dimension_errors:
        raise ValueError("Atlas dimension mismatch:\n" + "\n".join(dimension_errors[:20]))

    encoded = io.BytesIO()
    modified.save(encoded, format="DDS", pixel_format="DXT5")
    encoded_data = encoded.getvalue()
    enc_width, enc_height, enc_offset, enc_block_size = _dds_payload_info(encoded_data)
    if (enc_width, enc_height, enc_block_size) != (width, height, block_size):
        raise ValueError("Re-encoded DDS geometry differs from source")

    block_columns = math.ceil(width / 4)
    patched = bytearray(dds_data)
    for block_x, block_y in touched:
        index = block_y * block_columns + block_x
        source_offset = enc_offset + index * block_size
        target_offset = payload_offset + index * block_size
        patched[target_offset:target_offset + block_size] = encoded_data[source_offset:source_offset + block_size]

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / (atlas_name + ".xml")).write_bytes(xml_data)
    (target_dir / (atlas_name + ".dds")).write_bytes(patched)
    untouched_blocks = math.ceil(width / 4) * math.ceil(height / 4) - len(touched)
    return {
        "name": atlas_name,
        "size": [width, height],
        "entriesReplaced": replaced,
        "blocksPatched": len(touched),
        "blocksPreserved": untouched_blocks,
        "xmlSource": xml_package,
        "ddsSource": dds_package,
        "sourceXmlSha256": hashlib.sha256(xml_data).hexdigest(),
        "sourceDdsSha256": hashlib.sha256(dds_data).hexdigest(),
        "outputXmlSha256": hashlib.sha256(xml_data).hexdigest(),
        "outputDdsSha256": hashlib.sha256(patched).hexdigest(),
    }


def _write_package(stage: Path, package_path: Path) -> None:
    """Write a WoT resource package with streamable, uncompressed entries."""
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_STORED) as package:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(stage).as_posix())


def build_battle_atlas_addon(
    client: ClientData,
    contour_dir: Path,
    icons: dict[str, str],
    output_root: Path,
    generated_from: str,
    mod_version: str = __version__,
) -> tuple[Path, dict]:
    """Build the patch-specific classic players-panel add-on.

    Classic Scaleform panels never read the individual contour PNG URL. They
    draw a named sprite from ``battleAtlas``.  Rebuilding that one atlas is the
    conventional, code-free route used by current contour-icon mods.  It is
    deliberately kept in a separate package so the raw-PNG core remains valid
    across the 2.x client line.
    """
    stage = output_root / "battle-atlas-stage"
    if stage.exists():
        shutil.rmtree(stage)
    atlas_dir = stage / "res" / "gui" / "flash" / "atlases"
    atlas = build_atlas(client, "battleAtlas", contour_dir, icons, atlas_dir)
    manifest = {
        "modVersion": mod_version,
        "generatedFromClientVersion": generated_from,
        "compatibility": {
            "exactClientVersion": generated_from,
            "sourceXmlSha256": atlas["sourceXmlSha256"],
            "fallback": "Rebuild this add-on after a client atlas update",
        },
        "purpose": "Classic battle players-panel coloured contours",
        "containsVehicleNames": False,
        "atlases": [atlas],
    }
    (stage / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    meta = """<root>
  <id>com.rcooler.colored_contour_icons.battle_atlas</id>
  <version>{version}</version>
  <name>RCooLeR Colored Contour Icons - Battle Atlas</name>
  <description>Client-specific battleAtlas add-on for classic players panels.</description>
</root>
""".format(version=mod_version)
    (stage / "meta.xml").write_text(meta, encoding="utf-8", newline="\n")
    package_path = output_root / (
        "com.rcooler.colored_contour_icons_battle_atlas_%s_wg%s.wotmod"
        % (mod_version, generated_from)
    )
    _write_package(stage, package_path)
    return package_path, manifest


def build_runtime_fallback(icons: dict[str, str], stage: Path, output_root: Path, python2: Path) -> Path:
    """Build a tiny Python 2 client hook used only for post-update fallback icons."""
    source_dir = output_root / "runtime"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / "mod_colored_contour_icons.py"
    pyc_path = stage / "res" / "scripts" / "client" / "gui" / "mods" / "mod_colored_contour_icons.pyc"
    pyc_path.parent.mkdir(parents=True, exist_ok=True)

    known_names = tuple(sorted(icons))
    source = '''# -*- coding: ascii -*-
from __future__ import absolute_import

import logging

from items import vehicles
from gui.battle_control.arena_info import settings
import gui.shared.gui_items.Vehicle as vehicle_module


LOGGER = logging.getLogger('RCooLeRColoredContourIcons')
KNOWN_ICON_NAMES = frozenset(%r)
FALLBACK_ICON_NAMES = {
    'lightTank': 'ussr-R03_BT-7',
    'mediumTank': 'ussr-R04_T-34',
    'heavyTank': 'ussr-R01_IS',
    'AT-SPG': 'ussr-R02_SU-85',
    'SPG': 'ussr-R15_S-51',
}
FALLBACK_VEHICLE_NAMES = {
    'lightTank': 'ussr:R03_BT-7',
    'mediumTank': 'ussr:R04_T-34',
    'heavyTank': 'ussr:R01_IS',
    'AT-SPG': 'ussr:R02_SU-85',
    'SPG': 'ussr:R15_S-51',
}
VEHICLE_CLASSES = ('lightTank', 'mediumTank', 'heavyTank', 'AT-SPG', 'SPG')
CLASS_CACHE = {}


def _canonical_vehicle_name(vehicle_name):
    if ':' not in vehicle_name and '-' in vehicle_name:
        nation, identifier = vehicle_name.split('-', 1)
        return nation + ':' + identifier
    return vehicle_name


def _get_vehicle_class(vehicle_name):
    vehicle_name = _canonical_vehicle_name(vehicle_name)
    cached = CLASS_CACHE.get(vehicle_name)
    if cached is not None:
        return cached or None
    vehicle_class = ''
    try:
        nation_id, vehicle_type_id = vehicles.g_list.getIDsByName(vehicle_name)
        nation_list = vehicles.g_list.getList(nation_id)
        vehicle_info = nation_list.get(vehicle_type_id) if nation_list is not None else None
        if vehicle_info is not None:
            for candidate in VEHICLE_CLASSES:
                if candidate in vehicle_info.tags:
                    vehicle_class = candidate
                    break
    except Exception:
        LOGGER.debug('Could not classify new contour %%s', vehicle_name, exc_info=True)
    CLASS_CACHE[vehicle_name] = vehicle_class
    return vehicle_class or None


def _install():
    original_make_name = settings.makeVehicleIconName
    if not getattr(original_make_name, '_rcooler_colored_icons', False):
        def make_vehicle_icon_name(vehicle_name):
            icon_name = original_make_name(vehicle_name)
            if icon_name in KNOWN_ICON_NAMES:
                return icon_name
            return FALLBACK_ICON_NAMES.get(_get_vehicle_class(vehicle_name), icon_name)
        make_vehicle_icon_name._rcooler_colored_icons = True
        settings.makeVehicleIconName = make_vehicle_icon_name

    original_get_path = vehicle_module.getContourIconPath
    if not getattr(original_get_path, '_rcooler_colored_icons', False):
        def get_contour_icon_path(vehicle_name):
            icon_name = vehicle_name.replace(':', '-')
            if icon_name in KNOWN_ICON_NAMES:
                return original_get_path(vehicle_name)
            fallback_name = FALLBACK_VEHICLE_NAMES.get(_get_vehicle_class(vehicle_name))
            return original_get_path(fallback_name or vehicle_name)
        get_contour_icon_path._rcooler_colored_icons = True
        vehicle_module.getContourIconPath = get_contour_icon_path


try:
    _install()
except Exception:
    LOGGER.exception('Failed to install coloured contour fallback hook')
''' % (known_names,)
    source_path.write_text(source, encoding="ascii", newline="\n")
    result = subprocess.run(
        [str(python2), "-c", "import py_compile,sys; py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)", str(source_path), str(pyc_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("Python 2 runtime compilation failed:\n%s\n%s" % (result.stdout, result.stderr))
    return pyc_path


def build(
    game_root: Path,
    output_root: Path,
    palette_path: Path,
    include_atlases: bool = False,
    python2: Path | None = None,
    mod_version: str = __version__,
) -> dict:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", mod_version):
        raise ValueError("Invalid mod version: %r" % mod_version)
    client = ClientData(game_root)
    palette = _load_palette(palette_path)
    vehicles = client.vehicles()
    stage = output_root / "stage"
    contour_dir = stage / "res" / "gui" / "maps" / "icons" / "vehicle" / "contour"
    if stage.exists():
        shutil.rmtree(stage)
    contour_dir.mkdir(parents=True)

    counts: Counter[str] = Counter()
    unclassified: list[str] = []
    source_packages: Counter[str] = Counter()
    icon_manifest: dict[str, str] = {}
    alpha_errors: list[str] = []
    for resource_name, png_data, package_name in client.contours():
        vehicle = vehicles.get(resource_name)
        vehicle_class = vehicle.vehicle_class if vehicle is not None else CLASS_ALIASES.get(resource_name)
        if vehicle_class is None:
            unclassified.append(resource_name)
            continue
        source = Image.open(io.BytesIO(png_data)).convert("RGBA")
        result = recolor_contour(source, ramp_from_config(palette[vehicle_class]))
        if source.getchannel("A").tobytes() != result.getchannel("A").tobytes():
            alpha_errors.append(resource_name)
        result.save(contour_dir / (resource_name + ".png"), optimize=True, compress_level=9)
        counts[vehicle_class] += 1
        source_packages[package_name] += 1
        icon_manifest[resource_name] = vehicle_class

    generated_from = client.client_version()
    manifest = {
        "modVersion": mod_version,
        "compatibility": {
            "clientMajor": 2,
            "supportedVersions": "2.x",
            "fallback": "Unbundled vehicles use the standard client contour",
        },
        "generatedFromClientVersion": generated_from,
        "iconCount": sum(counts.values()),
        "countsByClass": dict(counts),
        "unclassifiedContours": unclassified,
        "alphaVerificationFailures": alpha_errors,
        "icons": icon_manifest,
    }
    if python2 is not None:
        runtime_path = build_runtime_fallback(icon_manifest, stage, output_root, python2)
        manifest["runtimeFallback"] = runtime_path.relative_to(stage).as_posix()
    with (stage / "manifest.json").open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)

    meta = """<root>
  <id>com.rcooler.colored_contour_icons</id>
  <version>{version}</version>
  <name>RCooLeR Colored Contour Icons</name>
  <description>Class-coloured vehicle contour icons generated from the current client.</description>
</root>
""".format(version=mod_version)
    (stage / "meta.xml").write_text(meta, encoding="utf-8", newline="\n")

    output_root.mkdir(parents=True, exist_ok=True)
    package_name = "com.rcooler.colored_contour_icons_%s" % mod_version
    package_path = output_root / (package_name + ".wotmod")
    # WoT resource packages are ZIP containers with stored entries. In particular,
    # large DDS atlases must not use Deflate: the client maps/streams these assets
    # and a compressed entry can turn startup into a several-minute stall.
    _write_package(stage, package_path)

    if include_atlases:
        atlas_package, atlas_manifest = build_battle_atlas_addon(
            client,
            contour_dir,
            icon_manifest,
            output_root,
            generated_from,
            mod_version=mod_version,
        )
        manifest["battleAtlasAddon"] = {
            "package": str(atlas_package),
            "containsVehicleNames": False,
            "atlas": atlas_manifest["atlases"][0],
        }

    build_preview(client, palette, output_root / "palette-preview.png")
    build_class_previews(contour_dir, icon_manifest, palette, output_root / "previews")
    manifest["package"] = str(package_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "build")
    parser.add_argument("--palette", type=Path, default=PROJECT_ROOT / "palette.json")
    parser.add_argument(
        "--include-atlases",
        action="store_true",
        help="Build a separate current-client battleAtlas add-on for classic ears",
    )
    parser.add_argument("--python2", type=Path)
    parser.add_argument(
        "--mod-version", default=__version__,
        help="Build an isolated release candidate without changing the stable source version",
    )
    arguments = parser.parse_args(argv)
    result = build(
        arguments.game_root,
        arguments.output,
        arguments.palette,
        include_atlases=arguments.include_atlases,
        python2=arguments.python2,
        mod_version=arguments.mod_version,
    )
    summary = {key: value for key, value in result.items() if key != "icons"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not result["alphaVerificationFailures"] else 2


if __name__ == "__main__":
    sys.exit(main())
