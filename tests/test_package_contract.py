import inspect
import json
import zipfile

import pytest

from colored_contour_icons import __version__
from colored_contour_icons.build import build, build_battle_atlas_addon


def test_builders_default_to_current_release_version():
    for builder in (build, build_battle_atlas_addon):
        assert inspect.signature(builder).parameters["mod_version"].default == __version__


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


def test_candidate_version_is_consistent_and_does_not_change_stable_version(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, root):
            pass

        def vehicles(self):
            return {}

        def contours(self):
            return iter(())

        def client_version(self):
            return "2.4.0.0"

    def fake_build_atlas(client, name, contour_dir, icons, target_dir):
        target_dir.mkdir(parents=True)
        (target_dir / "battleAtlas.xml").write_bytes(b"xml")
        (target_dir / "battleAtlas.dds").write_bytes(b"dds")
        return {"name": name, "sourceXmlSha256": "xml", "sourceDdsSha256": "dds"}

    monkeypatch.setattr("colored_contour_icons.build.ClientData", FakeClient)
    monkeypatch.setattr("colored_contour_icons.build.build_atlas", fake_build_atlas)
    monkeypatch.setattr("colored_contour_icons.build.build_preview", lambda *args: None)
    monkeypatch.setattr("colored_contour_icons.build.build_class_previews", lambda *args: None)
    palette = tmp_path / "palette.json"
    palette.write_text("{}")
    stable_version = __version__
    result = build(tmp_path, tmp_path / "output", palette,
                   include_atlases=True, mod_version="0.3.4-rc.1")
    from colored_contour_icons import __version__ as version_after_build
    assert version_after_build == stable_version
    for package_path in (result["package"], result["battleAtlasAddon"]["package"]):
        assert "0.3.4-rc.1" in package_path
        with zipfile.ZipFile(package_path) as archive:
            assert json.loads(archive.read("manifest.json"))["modVersion"] == "0.3.4-rc.1"
            assert b"<version>0.3.4-rc.1</version>" in archive.read("meta.xml")
            assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
            assert not any(name.endswith((".swf", ".pyc", ".py")) for name in archive.namelist())


@pytest.mark.parametrize("version", ["../escape", "0.3", "0.3.3/rc1", "0.3.3\\rc1"])
def test_invalid_candidate_version_is_rejected_before_writes(tmp_path, version):
    with pytest.raises(ValueError, match="Invalid mod version"):
        build(tmp_path, tmp_path / "output", tmp_path / "palette.json", mod_version=version)
    assert not (tmp_path / "output").exists()
