"""Compare client inputs and verify a resource-only contour candidate offline."""

import argparse
import hashlib
import io
import json
import math
import zipfile
from dataclasses import asdict
from pathlib import Path

from PIL import Image

from colored_contour_icons.build import _atlas_entries, _dds_payload_info
from colored_contour_icons.client import CLASS_ALIASES, ClientData
from colored_contour_icons.verify_atlas import verify_addon


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def compare_and_verify(baseline_root, candidate_root, core_path, addon_path):
    baseline, candidate = ClientData(baseline_root), ClientData(candidate_root)
    old_vehicles, new_vehicles = baseline.vehicles(), candidate.vehicles()
    old_contours = {name: data for name, data, _ in baseline.contours()}
    new_contours = {name: data for name, data, _ in candidate.contours()}
    resource = "gui/flash/atlases/battleAtlas."
    old_xml, _ = baseline.read_gui_resource(resource + "xml")
    new_xml, _ = candidate.read_gui_resource(resource + "xml")
    old_dds, _ = baseline.read_gui_resource(resource + "dds")
    new_dds, _ = candidate.read_gui_resource(resource + "dds")
    old_entries, new_entries = _atlas_entries(old_xml), _atlas_entries(new_xml)
    old_geometry = _dds_payload_info(old_dds)
    width, height, offset, block_size = _dds_payload_info(new_dds)
    report = {
        "baselineClient": baseline.client_version(),
        "candidateClient": candidate.client_version(),
        "vehicles": {
            "baselineCount": len(old_vehicles), "candidateCount": len(new_vehicles),
            "added": [asdict(new_vehicles[name]) for name in sorted(new_vehicles.keys() - old_vehicles.keys())],
            "removed": sorted(old_vehicles.keys() - new_vehicles.keys()),
            "changed": [
                {"before": asdict(old_vehicles[name]), "after": asdict(new_vehicles[name])}
                for name in sorted(old_vehicles.keys() & new_vehicles.keys())
                if old_vehicles[name] != new_vehicles[name]
            ],
        },
        "contours": {
            "baselineCount": len(old_contours), "candidateCount": len(new_contours),
            "added": sorted(new_contours.keys() - old_contours.keys()),
            "removed": sorted(old_contours.keys() - new_contours.keys()),
            "changed": [name for name in sorted(old_contours.keys() & new_contours.keys())
                        if old_contours[name] != new_contours[name]],
        },
        "atlas": {
            "baselineGeometry": list(old_geometry[:2]), "candidateGeometry": [width, height],
            "baselineEntryCount": len(old_entries), "candidateEntryCount": len(new_entries),
            "baselineXmlSha256": sha256(old_xml), "candidateXmlSha256": sha256(new_xml),
            "baselineDdsSha256": sha256(old_dds), "candidateDdsSha256": sha256(new_dds),
            "addedEntries": sorted(new_entries.keys() - old_entries.keys()),
            "removedEntries": sorted(old_entries.keys() - new_entries.keys()),
            "movedOrResizedEntries": sum(old_entries[name] != new_entries[name]
                                        for name in old_entries.keys() & new_entries.keys()),
        },
    }
    verify_addon(candidate_root, addon_path)
    expected_icons = {
        name: new_vehicles[name].vehicle_class if name in new_vehicles else CLASS_ALIASES[name]
        for name in new_contours if name in new_vehicles or name in CLASS_ALIASES
    }
    touched = set()
    columns = math.ceil(width / 4)
    with zipfile.ZipFile(core_path) as core, zipfile.ZipFile(addon_path) as addon:
        core_manifest = json.loads(core.read("manifest.json"))
        addon_manifest = json.loads(addon.read("manifest.json"))
        assert core_manifest["icons"] == expected_icons, "Candidate omits/misclassifies contours"
        assert core_manifest["modVersion"] == addon_manifest["modVersion"], "Package versions differ"
        for archive in (core, addon):
            assert archive.testzip() is None, "ZIP CRC failure"
            assert all(entry.compress_type == zipfile.ZIP_STORED for entry in archive.infolist())
            assert not any(name.endswith((".py", ".pyc", ".swf")) for name in archive.namelist())
            assert not any("vehicleMarkerAtlas" in name for name in archive.namelist())
        prefix = "res/gui/maps/icons/vehicle/contour/"
        assert set(core.namelist()) == {"meta.xml", "manifest.json"} | {
            prefix + name + ".png" for name in expected_icons
        }
        assert set(addon.namelist()) == {
            "meta.xml", "manifest.json", "res/" + resource + "xml", "res/" + resource + "dds"
        }
        for name in expected_icons:
            original = Image.open(io.BytesIO(new_contours[name])).convert("RGBA")
            coloured = Image.open(io.BytesIO(core.read(prefix + name + ".png"))).convert("RGBA")
            assert original.size == coloured.size, "Contour size changed: " + name
            assert original.getchannel("A").tobytes() == coloured.getchannel("A").tobytes(), name
            if name not in new_entries:
                continue
            x, y, icon_width, icon_height = new_entries[name]
            assert original.size == (icon_width, icon_height), "Atlas geometry differs: " + name
            for block_y in range(y // 4, math.ceil((y + icon_height) / 4)):
                for block_x in range(x // 4, math.ceil((x + icon_width) / 4)):
                    touched.add(block_y * columns + block_x)
        assert addon.read("res/" + resource + "xml") == new_xml, "Atlas XML modified"
        patched = addon.read("res/" + resource + "dds")
        assert len(patched) == len(new_dds)
        assert patched[:offset] == new_dds[:offset], "DDS header modified"
        actual_changes = set()
        for index in range((len(new_dds) - offset) // block_size):
            start = offset + index * block_size
            if new_dds[start:start + block_size] != patched[start:start + block_size]:
                actual_changes.add(index)
        assert actual_changes <= touched, "Non-contour atlas blocks modified"
    report["verification"] = {
        "modVersion": core_manifest["modVersion"], "iconsVerified": len(expected_icons),
        "unclassifiedNativeFallbacks": sorted(new_contours.keys() - expected_icons.keys()),
        "atlasHeaderAndXmlUnchanged": True, "alphaAndDimensionsPreserved": True,
        "codeFreeStoredPackages": True, "atlasContourBlocks": len(touched),
        "atlasChangedBlocks": len(actual_changes),
        "atlasNonContourBlocksPreserved": (len(new_dds) - offset) // block_size - len(touched),
        "coreSha256": sha256(core_path.read_bytes()), "addonSha256": sha256(addon_path.read_bytes()),
    }
    return report


def main():
    if not __debug__:
        raise RuntimeError("Run this verifier without Python -O; safety assertions must be enabled")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare_and_verify(args.baseline, args.candidate, args.core, args.addon)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
