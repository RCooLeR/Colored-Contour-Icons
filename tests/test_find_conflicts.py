import zipfile

from colored_contour_icons.find_conflicts import find_conflicts


def test_find_conflicts_reports_other_atlas_packages_only(tmp_path):
    target = tmp_path / "target.wotmod"
    target.touch()
    conflict = tmp_path / "conflict.wotmod"
    with zipfile.ZipFile(conflict, "w") as archive:
        archive.writestr("res/gui/flash/atlases/battleAtlas.dds", b"dds")
    unrelated = tmp_path / "unrelated.wotmod"
    with zipfile.ZipFile(unrelated, "w") as archive:
        archive.writestr("res/gui/other.png", b"png")
    assert find_conflicts(tmp_path, target) == [str(conflict)]
