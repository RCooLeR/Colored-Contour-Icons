import io
import subprocess
import sys
import zipfile

import pytest
from PIL import Image

from colored_contour_icons.client import ClientData
from colored_contour_icons.verify_atlas import _read_client_gui_resource


def client_root(tmp_path):
    (tmp_path / "res" / "packages").mkdir(parents=True)
    return tmp_path


def test_client_metadata_wins_over_stale_or_future_mod_directories(tmp_path):
    root = client_root(tmp_path)
    (root / "version.xml").write_text(
        "<version.xml><version> v.2.4.0.0 #5419 </version></version.xml>"
    )
    (root / "mods" / "2.3.1.3").mkdir(parents=True)
    (root / "mods" / "2.9.0.0").mkdir()
    assert ClientData(root).client_version() == "2.4.0.0"


def test_preloaded_client_needs_no_mod_directory(tmp_path):
    root = client_root(tmp_path)
    (root / "version.xml").write_text(
        "<version.xml><version> v.2.4.0.0 #5419 </version></version.xml>"
    )
    assert ClientData(root).client_version() == "2.4.0.0"


@pytest.mark.parametrize("metadata", [
    None, "<broken", "<root><version>unknown</version></root>",
    "<root><version>v.2.4.0.0.1 #930</version></root>",
])
def test_missing_or_invalid_metadata_falls_back_to_numeric_mod_directory(tmp_path, metadata):
    root = client_root(tmp_path)
    if metadata is not None:
        (root / "version.xml").write_text(metadata)
    for version in ("2.3.1.3", "2.10.0.0", "2.9.0.0"):
        (root / "mods" / version).mkdir(parents=True)
    assert ClientData(root).client_version() == "2.10.0.0"


def test_version_detection_requires_evidence(tmp_path):
    with pytest.raises(FileNotFoundError, match="active client version"):
        ClientData(client_root(tmp_path)).client_version()


def test_gui_package_parts_use_numeric_precedence(tmp_path):
    root = client_root(tmp_path)
    contour = "gui/maps/icons/vehicle/contour/ussr-R01_IS.png"
    resource = "gui/flash/atlases/battleAtlas.xml"
    for part in (2, 9, 10):
        png = io.BytesIO()
        Image.new("RGBA", (1, 1), (part, 0, 0, 255)).save(png, format="PNG")
        with zipfile.ZipFile(root / "res" / "packages" / ("gui-part%d.pkg" % part), "w") as archive:
            archive.writestr(contour, png.getvalue())
            archive.writestr(resource, str(part).encode("ascii"))
    client = ClientData(root)
    assert client.read_gui_resource(resource) == (b"10", "gui-part10.pkg")
    assert client.contour_image("ussr-R01_IS").getpixel((0, 0)) == (10, 0, 0, 255)
    contours = list(client.contours())
    assert len(contours) == 1
    assert contours[0][2] == "gui-part10.pkg"
    assert _read_client_gui_resource(root, resource) == b"10"


def test_contour_generation_opens_each_package_only_once(tmp_path, monkeypatch):
    root = client_root(tmp_path)
    package_path = root / "res" / "packages" / "gui-part1.pkg"
    with zipfile.ZipFile(package_path, "w") as archive:
        for name in ("tank_a", "tank_b", "tank_c"):
            archive.writestr("gui/maps/icons/vehicle/contour/%s.png" % name, b"png")
    original_zipfile = zipfile.ZipFile
    opened = []

    def counted_zipfile(path, *args, **kwargs):
        opened.append(path)
        return original_zipfile(path, *args, **kwargs)

    monkeypatch.setattr("colored_contour_icons.client.zipfile.ZipFile", counted_zipfile)
    assert len(list(ClientData(root).contours())) == 3
    assert opened == [package_path]


def test_install_verifier_does_not_require_pillow():
    result = subprocess.run([
        sys.executable, "-c",
        "import colored_contour_icons.verify_atlas; import sys; assert 'PIL' not in sys.modules",
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
