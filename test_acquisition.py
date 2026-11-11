from pathlib import Path
import unittest
from fnirsi_decode import decode
from acquisition import fields
class AcquisitionTests(unittest.TestCase):
    def test_reference_lane_paths_and_no_assumed_filters(self):
        for name,lanes in [('3',8),('6',8),('7',4)]:
            with self.subTest(name=name):
                m,_=decode((Path(__file__).parent/'examples/reference'/f'{name}.wav').read_bytes())
                a=m['acquisition'];self.assertEqual(a['input_lanes_per_channel'],lanes)
                self.assertTrue(a['channel_path_matches_enabled_channels'])
                self.assertIsNone(a['moving_average_window']);self.assertIsNone(a['pair_smoothing_enabled'])
    def test_inconsistent_path_is_not_generalized(self):
        d=bytearray(0x220);d[0xa5]=2
        a=fields(d,{'sections':[{'offset':50,'length':len(d)-50}],'channel_flag_bytes':[1,1]})
        self.assertFalse(a['channel_path_matches_enabled_channels']);self.assertIsNone(a['input_lanes_per_channel'])
    def test_short_settings_cannot_read_preview_as_controls(self):
        a=fields(bytes(0x300),{'sections':[{'offset':50,'length':10}]})
        self.assertNotIn('averaging_control_raw',a)
    def test_control_metadata_does_not_modify_saved_samples(self):
        d=bytearray((Path(__file__).parent/'examples/reference/7.wav').read_bytes())
        before,samples=decode(d);d[0x21d]=8
        after,other=decode(d)
        self.assertEqual(samples,other)
        self.assertEqual(before['calibration'],after['calibration'])
        self.assertEqual(after['acquisition']['averaging_control_raw'],8)
