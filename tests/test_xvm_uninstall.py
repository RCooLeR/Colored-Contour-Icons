from colored_contour_icons.xvm_uninstall import remove_adapter_references


def test_remove_adapter_references_is_narrow_and_idempotent():
    source = '''"extraFieldsLeft": [
  ${"_rcooler_colored_contour_icons.xc":"fields.vehicleIconLeft"},
  ${"_rcooler_colored_contour_icons.xc":"fields.compactVehicleNameLeft"},
  ${"def.hpBar"}
]'''
    cleaned = remove_adapter_references(source)
    assert "rcooler" not in cleaned
    assert '${"def.hpBar"}' in cleaned
    assert remove_adapter_references(cleaned) == cleaned
