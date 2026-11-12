import unittest
from decoder.timing import trigger_fields,origin_sample
class FirmwareMarkerTests(unittest.TestCase):
    def fields(self,offset=-199,width=950):
        d=bytearray(0x200)
        d[0x36:0x38]=width.to_bytes(2,'big')
        for at,value in [(0x190,100),(0x1af,100),(0x17e,offset),(0x1c8,0)]:
            d[at:at+8]=value.to_bytes(8,'big',signed=True)
        return trigger_fields(d,{'samples_per_pixel_candidate':25},23752)
    def test_negative_division_truncates_toward_zero(self):
        f=self.fields();self.assertEqual(f['display_marker_pixel'],474)
        self.assertAlmostEqual(f['display_marker_fractional_pixel'],473.01)
    def test_positive_fraction_and_geometry(self):
        self.assertEqual(self.fields(199,800)['display_marker_pixel'],401)
    def test_display_pan_does_not_shift_retained_origin(self):
        a,b=self.fields(-199),self.fields(999)
        self.assertEqual(a['sample_index_candidate'],b['sample_index_candidate'])
        self.assertEqual(origin_sample({'calibration':{'trigger':a}},'trigger marker'),11875)
    def test_hardware_instant_never_invented(self):
        self.assertIsNone(self.fields()['hardware_trigger_sample_index'])
    def test_short_unknown_spacing(self):
        self.assertEqual(trigger_fields(bytes(100),{},100),{})
        self.assertEqual(trigger_fields(bytes(0x200),{'samples_per_pixel_candidate':12},100),{})

class AlignmentMetadataTests(unittest.TestCase):
    def test_signed_correction_is_diagnostic_only(self):
        d=bytearray(0x200)
        for at in (0x190,0x1af):d[at:at+8]=(100).to_bytes(8,'big')
        d[0x113:0x115]=(-37).to_bytes(2,'big',signed=True)
        f=trigger_fields(d,{'samples_per_pixel_candidate':25},23752)
        self.assertEqual(f['primary_alignment_correction_samples'],-37)
        self.assertIsNone(f['secondary_alignment_correction_samples'])
        self.assertEqual(f['sample_index_candidate'],11875)
