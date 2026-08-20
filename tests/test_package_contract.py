import zipfile

from colored_contour_icons import __version__
from colored_contour_icons.build import build_battle_atlas_addon


def test_ears_release_version_is_current():
    assert __version__ == "0.3.2"


def test_battle_atlas_addon_contains_no_code_or_marker_atlas(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "battleAtlas.xml").write_bytes(b"xml")
    (source / "battleAtlas.dds").write_bytes(b"dds")

    def fake_build_atlas(client, name, contour_dir, icons, target_dir):
        target_dir.mkdir(parents=True)
        (target_dir / "battleAtlas.xml").write_bytes(b"xml")
        (target_dir / "battleAtlas.dds").write_bytes(b"dds")
        return {
            "name": "battleAtlas",
            "sourceXmlSha256": "xml-hash",
            "sourceDdsSha256": "dds-hash",
        }

    monkeypatch.setattr("colored_contour_icons.build.build_atlas", fake_build_atlas)
    package, _ = build_battle_atlas_addon(
        object(), source, {}, tmp_path / "output", "2.3.1.3"
    )
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert "res/gui/flash/atlases/battleAtlas.xml" in names
    assert "res/gui/flash/atlases/battleAtlas.dds" in names
    assert not any("vehicleMarkerAtlas" in name for name in names)
    assert not any(name.endswith((".swf", ".pyc")) for name in names)
