# Розробка RCooLeR Colored Contour Icons

## Збірка

Потрібні Python 3.10+, Pillow 12 та Python 2.7 для компіляції необов’язкового
runtime-fallback. Приклад:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m colored_contour_icons.build `
  --game-root 'D:\Games\World_of_Tanks' `
  --output "$PWD\build" `
  --include-atlases
```

Параметр `--include-atlases` створює окремий add-on лише з `battleAtlas`.
`vehicleMarkerAtlas`, маркери над технікою, Python і SWF до нього не входять.

## Походження формату

Реалізація читання BXML заснована на описі формату з GPL-3.0 проєкту
[TankIconMaker / WotDataLib](https://github.com/ktkr3d/TankIconMaker), який
посилається на World of Tanks Mod Tools від KatzSmile. Проєкт поширюється за
умовами GNU GPL v3.
