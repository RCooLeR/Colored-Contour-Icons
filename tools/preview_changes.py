"""Render an original/coloured comparison sheet for newly added client contours."""

import argparse
import io
import json
import math
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from colored_contour_icons.build import PROJECT_ROOT, _font
from colored_contour_icons.client import ClientData


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--build-output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.build_output / "compatibility-audit.json").read_text(encoding="utf-8"))
    names = report["contours"]["added"]
    if not names:
        raise ValueError("This candidate has no newly added contours")
    version = report["verification"]["modVersion"]
    source = {name: data for name, data, _ in ClientData(args.candidate).contours() if name in names}
    palette = json.loads((PROJECT_ROOT / "palette.json").read_text(encoding="utf-8"))
    columns, cell_width, cell_height, header = 3, 570, 145, 85
    canvas = Image.new("RGB", (columns * cell_width, header + math.ceil(len(names) / columns) * cell_height), "#17191D")
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 14), "Colored Contour Icons %s — WoT %s" % (version, report["candidateClient"]),
              font=_font(25, True), fill="#F2F2F2")
    draw.text((20, 49), "%d added contours | original left / coloured right | 3x nearest-neighbour" % len(names),
              font=_font(17), fill="#B8BDC5")
    with zipfile.ZipFile(args.build_output / ("com.rcooler.colored_contour_icons_%s.wotmod" % version)) as archive:
        classes = json.loads(archive.read("manifest.json"))["icons"]
        for index, name in enumerate(names):
            x = (index % columns) * cell_width
            y = header + (index // columns) * cell_height
            draw.rectangle((x + 5, y + 4, x + cell_width - 5, y + cell_height - 4), fill="#101216", outline="#343840")
            draw.text((x + 15, y + 12), name, font=_font(13), fill="#D9DCE1")
            draw.text((x + 15, y + 121), classes[name], font=_font(14, True), fill=palette[classes[name]]["highlight"])
            original = Image.open(io.BytesIO(source[name])).convert("RGBA")
            coloured = Image.open(io.BytesIO(archive.read("res/gui/maps/icons/vehicle/contour/" + name + ".png"))).convert("RGBA")
            for dx, icon in ((17, original), (300, coloured)):
                resized = icon.resize((icon.width * 3, icon.height * 3), Image.Resampling.NEAREST)
                canvas.paste(resized, (x + dx, y + 39), resized)
    target = args.build_output / "new-vehicle-contours.png"
    canvas.save(target, optimize=True)
    print(target)


if __name__ == "__main__":
    main()
