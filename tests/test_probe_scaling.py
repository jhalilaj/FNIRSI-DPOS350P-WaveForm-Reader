"""Probe-setting tests using firmware-style changes to saved ranges/readouts."""
from pathlib import Path
import unittest
from decoder.fnirsi_decode import decode, channel_samples
from decoder.calibration import volts

FIXTURE = Path(__file__).parent / "fixtures/reference/7.wav"


def scaled_capture(factors):
    data = bytearray(FIXTURE.read_bytes())
    metadata, _ = decode(data)
    trailer = metadata["sections"][0]["offset"] + metadata["sections"][0]["length"] - 240
    for i, factor in enumerate(factors):
        shift = i * 0x41
        data[0x67 + shift] = {1: 0, 10: 1, 100: 2}[factor]
        # Like firmware: range and voltage readouts scale, sample coordinates do not.
        for offset in (0x6D + shift, 0x75 + shift):
            value = int.from_bytes(data[offset:offset+8], "big")
            data[offset:offset+8] = (value * factor).to_bytes(8, "big")
        for j in range(6):
            offset = trailer + i*96 + j*8
            value = int.from_bytes(data[offset:offset+8], "big", signed=True)
            data[offset:offset+8] = (value * factor).to_bytes(8, "big", signed=True)
    return data


class ProbeScalingTests(unittest.TestCase):
    def test_independent_probe_factors_without_double_scaling(self):
        baseline, raw = decode(FIXTURE.read_bytes())
        original = volts(baseline, channel_samples(baseline, raw))
        for factors in ((1, 1), (10, 100), (100, 10)):
            with self.subTest(factors=factors):
                metadata, samples = decode(scaled_capture(factors))
                channels = channel_samples(metadata, samples)
                self.assertEqual(channels, channel_samples(baseline, raw))
                converted = volts(metadata, channels)
                for i, name in enumerate(("CH1", "CH2")):
                    info = metadata["calibration"]["channels"][name]
                    self.assertEqual(info["probe_factor"], factors[i])
                    self.assertEqual(info["probe_label"], f"{factors[i]}X")
                    for index in (0, 6000, 12000, 18000):
                        self.assertAlmostEqual(converted[name][index], original[name][index]*factors[i])

    def test_100x_accepts_saved_range_above_old_1000_v_limit(self):
        data = scaled_capture((100, 100))
        metadata, _ = decode(data)
        trailer = metadata["sections"][0]["offset"] + metadata["sections"][0]["length"] - 240
        # A 25 V/div input range at 100X is saved as 2500 V/div.
        for offset in (0x6D, 0x75):
            data[offset:offset+8] = (2500_000_000).to_bytes(8, "big")
        for j in range(6):
            offset = trailer + j*8
            value = int.from_bytes(data[offset:offset+8], "big", signed=True)
            data[offset:offset+8] = (value*25).to_bytes(8, "big", signed=True)
        metadata, _ = decode(data)
        self.assertTrue(metadata["calibration"]["channels"]["CH1"]["conversion_usable"])

    def test_unknown_probe_setting_keeps_raw_only(self):
        data = scaled_capture((1, 1))
        data[0x67] = 3
        metadata, samples = decode(data)
        self.assertIsNone(metadata["calibration"]["channels"]["CH1"]["probe_factor"])
        with self.assertRaises(ValueError):
            volts(metadata, channel_samples(metadata, samples))
