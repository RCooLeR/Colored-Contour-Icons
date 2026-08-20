import unittest

from PIL import Image

from colored_contour_icons.render import ToneRamp, recolor_contour


class RecolourTests(unittest.TestCase):
    def test_recolour_preserves_dimensions_and_alpha(self):
        source = Image.new("RGBA", (3, 2))
        source.putdata([
            (0, 0, 0, 0), (40, 50, 60, 31), (120, 130, 140, 127),
            (180, 170, 160, 191), (255, 255, 255, 255), (20, 25, 30, 6),
        ])
        result = recolor_contour(
            source,
            ToneRamp((10, 20, 30), (80, 100, 120), (220, 230, 240)),
        )
        self.assertEqual(result.size, source.size)
        self.assertEqual(result.getchannel("A").tobytes(), source.getchannel("A").tobytes())
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
