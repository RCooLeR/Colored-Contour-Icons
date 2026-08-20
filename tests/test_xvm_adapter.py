import json

import pytest

from colored_contour_icons.xvm_adapter import (
    DEFAULT_FRAGMENT,
    AdapterError,
    patch_players_panel,
    prepare_adapter,
)


SAMPLE_PLAYERS_PANEL = r'''
{
  // A deliberately small default-style XVM 13.1 players panel.
  "playersPanel": {
    "none": {
      "extraFields": {
        "leftPanel": { "formats": [] },
        "rightPanel": { "formats": [] }
      }
    },
    "short": {
      "standardFields": [ "frags" ],
      "extraFieldsLeft": [ ${"def.existing"} ],
      "extraFieldsRight": [ ${"def.existing"} ]
    },
    "medium": {
      "standardFields": [ "frags", "badge", "nick" ],
      "extraFieldsLeft": [ ${"def.existing"} ],
      "extraFieldsRight": [ ${"def.existing"} ]
    },
    "medium2": {
      "standardFields": [ "frags", "vehicle" ],
      "extraFieldsLeft": [ ${"def.existing"} ],
      "extraFieldsRight": [ ${"def.existing"} ]
    },
    "large": {
      "standardFields": [ "frags", "nick", "vehicle" ],
      "extraFieldsLeft": [ ${"def.existing"} ],
      "extraFieldsRight": [ ${"def.existing"} ]
    }
  }
}
'''


def test_default_xvm_players_panel_is_patched_idempotently():
    patched = patch_players_panel(SAMPLE_PLAYERS_PANEL)

    assert patched.count('"fields.vehicleIconLeft"') == 4
    assert patched.count('"fields.vehicleIconRight"') == 4
    assert '"fields.compactVehicleNameLeft"' not in patched
    assert '"fields.compactVehicleNameRight"' not in patched
    assert patch_players_panel(patched) == patched


def test_compact_modes_keep_width_and_receive_name_overlay():
    patched = patch_players_panel(SAMPLE_PLAYERS_PANEL, include_names=True)

    assert '"standardFields": [ "frags" ]' in patched
    assert '"standardFields": [ "frags", "badge", "nick" ]' in patched
    assert patched.count('"fields.compactVehicleNameLeft"') == 2
    assert patched.count('"fields.compactVehicleNameRight"') == 2
    assert patch_players_panel(patched, include_names=True) == patched


def test_none_mode_is_untouched():
    patched = patch_players_panel(SAMPLE_PLAYERS_PANEL)

    assert '"leftPanel": { "formats": [] }' in patched
    assert '"rightPanel": { "formats": [] }' in patched
    assert "noneVehicle" not in patched


def test_compact_name_fields_cover_the_same_icon_area_on_both_sides():
    fragment = json.loads(DEFAULT_FRAGMENT.read_text(encoding="utf-8"))
    left = fragment["fields"]["compactVehicleNameLeft"]
    right = fragment["fields"]["compactVehicleNameRight"]

    assert (left["x"], left["width"], left["height"]) == (40, 80, 22)
    assert (right["x"], right["width"], right["height"]) == (-40, 80, 22)
    assert left["align"] == right["align"] == "center"
    assert left["bindToIcon"] is right["bindToIcon"] is True


def test_icon_fields_are_side_specific_for_future_mirroring_support():
    fragment = json.loads(DEFAULT_FRAGMENT.read_text(encoding="utf-8"))

    assert fragment["fields"]["vehicleIconLeft"]["bindToIcon"] is True
    assert fragment["fields"]["vehicleIconRight"]["bindToIcon"] is True


def test_preparer_refuses_to_overwrite_source_profile(tmp_path):
    players_panel = tmp_path / "playersPanel.xc"
    players_panel.write_text(SAMPLE_PLAYERS_PANEL, encoding="utf-8")

    with pytest.raises(AdapterError, match="source profile"):
        prepare_adapter(players_panel, tmp_path)
