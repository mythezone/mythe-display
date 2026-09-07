"""Validate the hardware-specific EDID without requiring a display or root."""

from pathlib import Path
import unittest


class DisplayEdidTest(unittest.TestCase):
    def test_native_hdmi_mode_and_basic_audio(self):
        path = Path(__file__).resolve().parents[1] / "config/edid/mythe-display-3840x1100.hex"
        edid = bytes.fromhex(path.read_text())
        self.assertEqual(edid[:8], b"\x00\xff\xff\xff\xff\xff\xff\x00")
        self.assertEqual(len(edid), (edid[126] + 1) * 128)
        self.assertEqual(len(edid), 256)
        for offset in range(0, len(edid), 128):
            self.assertEqual(sum(edid[offset:offset + 128]) % 256, 0)
        timing = edid[54:72]
        self.assertEqual(timing[2] | ((timing[4] & 0xf0) << 4), 3840)
        self.assertEqual(timing[5] | ((timing[7] & 0xf0) << 4), 1100)
        pixel_clock_khz = int.from_bytes(timing[:2], "little") * 10
        self.assertGreater(pixel_clock_khz, 165000)
        cta = edid[128:]
        self.assertEqual(cta[:2], b"\x02\x03")
        self.assertTrue(cta[3] & 0x40)  # Basic two-channel audio.
        blocks = {}
        offset = 4
        while offset < cta[2]:
            tag, length = cta[offset] >> 5, cta[offset] & 31
            self.assertGreater(length, 0)
            self.assertLessEqual(offset + 1 + length, cta[2])
            blocks[tag] = cta[offset + 1:offset + 1 + length]
            offset += 1 + length
        self.assertEqual(blocks[3][:3], b"\x03\x0c\x00")  # HDMI OUI, not DVI.
        self.assertGreaterEqual(blocks[3][6] * 5000, pixel_clock_khz)
        self.assertEqual(blocks[1], b"\x09\x07\x01")  # LPCM stereo, 32/44.1/48 kHz, 16 bit.
        self.assertEqual(blocks[7], b"\x00\x4a")  # VCDB: RGB quantization, underscan.
        self.assertNotIn(2, blocks)  # No unreliable VIC list from the original extension.


if __name__ == "__main__":
    unittest.main()
