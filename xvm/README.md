# Optional XVM ears adapter

XVM 13.1.0 renders the side players panels from `battleAtlas`, even when the
same vehicle is successfully loaded from a raw contour PNG elsewhere. This
adapter overlays the raw resource
`img://gui/maps/icons/vehicle/contour/{{vehiclename}}.png` at XVM's vehicle-icon
anchor. The original atlas sprite remains underneath, so an icon that is not in
the mod still uses the client's normal contour.

The adapter is deliberately separate from the `.wotmod`. XVM configuration is
a user-owned physical profile under `res_mods/configs/xvm`; it is not safely
replaceable from a resource package.

## Prepare a review copy

The preparer never modifies the selected profile. It writes a patched
`playersPanel.xc` and `_rcooler_colored_contour_icons.xc` beside each other in a
staging directory:

```powershell
.\tools\prepare-xvm-adapter.ps1 `
  -PlayersPanel 'D:\Games\World_of_Tanks\res_mods\configs\xvm\default\playersPanel.xc'
```

If a Python launcher with arguments is used, invoke the module directly:

```powershell
$env:PYTHONPATH = "$PWD\src"
py -3 -m colored_contour_icons.xvm_adapter `
  --players-panel 'D:\Games\World_of_Tanks\res_mods\configs\xvm\default\playersPanel.xc'
```

Review the generated file before copying both files into the directory that
contains the active profile's `playersPanel.xc`.

The preparer makes only these changes:

- adds one imported image field to the left and right `extraFields` arrays for
  `short`, `medium`, `medium2`, and `large`;
- adds a compact imported vehicle-name field directly over the 80×24 icon area
  in `short` and `medium`, where default XVM has no vehicle-name field.

The `standardFields` arrays and the `none` mode are not changed, so compact
panels retain their original widths and the hidden mode retains its original
appearance.

All existing fields, formatting, comments, and mode options are retained. If a
profile imports a whole mode from another file, the preparer stops instead of
guessing; prepare that mode's source file or add the references manually.

## Limits

- Coordinates match default XVM 13.1.0 with `battle.mirroredVehicleIcons: true`.
  A profile that disables mirroring needs a visually checked right-side image;
  the compact text already has separate left/right coordinates.
- The compact label is deliberately limited to 12 characters and 80 pixels.
  Long localized vehicle names are truncated with `..` to avoid widening the
  panel or covering the adjacent frag/name fields.
- The native atlas icon remains underneath as the missing-PNG fallback. This is
  conservative, but overlapping antialiased edges can look slightly heavier.
- XVM config imports are resolved relative to `playersPanel.xc`, so the fragment
  must stay beside that file.
