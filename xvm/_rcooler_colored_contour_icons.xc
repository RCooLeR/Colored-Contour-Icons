{
  "fields": {
    "vehicleIconLeft": {
      "enabled": true,
      "x": 0,
      "y": 0,
      "align": "left",
      "valign": "top",
      "bindToIcon": true,
      "alpha": "{{alive?100|50}}",
      "layer": "normal",
      "src": "img://gui/maps/icons/vehicle/contour/{{vehiclename}}.png"
    },
    "vehicleIconRight": {
      "enabled": true,
      "x": 0,
      "y": 0,
      "align": "left",
      "valign": "top",
      "bindToIcon": true,
      "alpha": "{{alive?100|50}}",
      "layer": "normal",
      "src": "img://gui/maps/icons/vehicle/contour/{{vehiclename}}.png"
    },
    "compactVehicleNameLeft": {
      "enabled": true,
      "x": 40,
      "y": 1,
      "width": 80,
      "height": 22,
      "align": "center",
      "valign": "top",
      "bindToIcon": true,
      "layer": "top",
      "textFormat": {
        "font": "$FieldFont",
        "size": 11,
        "color": "0xF2F2F2",
        "align": "center",
        "bold": true,
        "valign": "center"
      },
      "format": "<font alpha='{{alive?#FF|#80}}'>{{vehicle%.12s~..}}</font>",
      "shadow": {
        "enabled": true,
        "distance": 0,
        "angle": 0,
        "color": "0x000000",
        "alpha": 100,
        "blur": 4,
        "strength": 1.5
      }
    },
    "compactVehicleNameRight": {
      "enabled": true,
      "x": -40,
      "y": 1,
      "width": 80,
      "height": 22,
      "align": "center",
      "valign": "top",
      "bindToIcon": true,
      "layer": "top",
      "textFormat": {
        "font": "$FieldFont",
        "size": 11,
        "color": "0xF2F2F2",
        "align": "center",
        "bold": true,
        "valign": "center"
      },
      "format": "<font alpha='{{alive?#FF|#80}}'>{{vehicle%.12s~..}}</font>",
      "shadow": {
        "enabled": true,
        "distance": 0,
        "angle": 0,
        "color": "0x000000",
        "alpha": 100,
        "blur": 4,
        "strength": 1.5
      }
    }
  }
}
