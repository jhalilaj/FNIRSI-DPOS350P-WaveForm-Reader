from pathlib import Path
import unittest,struct
from decoder.fnirsi_decode import decode
class CompatibilityTests(unittest.TestCase):
    def data(self):return bytearray((Path(__file__).parent/'fixtures/reference/7.wav').read_bytes())
    def test_match_does_not_invent_firmware_identity(self):
        m,_=decode(self.data());c=m['compatibility']
        self.assertTrue(c['numeric_model_allowed']);self.assertIsNone(c['producer_firmware_version'])
        self.assertFalse(c['cross_version_validation'])
    def test_unknown_geometry_preserves_samples_disables_physical_model(self):
        d=self.data();before,samples=decode(d);d[0x4a:0x4c]=(96).to_bytes(2,'big')
        after,other=decode(d)
        self.assertEqual(samples,other)
        self.assertFalse(after['compatibility']['numeric_model_allowed'])
        self.assertNotIn('sample_interval_s_candidate',after['calibration'])
        self.assertNotIn('viewport_samples',after['saved_display'])
    def test_shifted_settings_tail_cannot_be_mistaken_for_readouts(self):
        d=self.data();header=list(struct.unpack_from('>7I',d));at=header[2]
        d[at:at]=b'xx'
        header[1]+=2;header[2]+=2;header[4]+=2;header[6]+=2
        struct.pack_into('>7I',d,0,*header)
        m,_=decode(d)
        self.assertFalse(m['compatibility']['settings_layout_matched'])
        self.assertNotIn('channels',m['calibration'])
    def test_changed_frame_count_without_layout_change_rejected_for_units(self):
        d=self.data();d[0x1a4:0x1a6]=(50).to_bytes(2,'big')
        m,_=decode(d);self.assertFalse(m['compatibility']['numeric_model_allowed'])
