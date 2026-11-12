import unittest
from decoder.firmware_timing import acquisition_positions,retained_address_index,forward_average_interior
class TimingPathTests(unittest.TestCase):
    def test_signed_nested_rounding_and_positive_ring_endpoint(self):
        p=acquisition_positions(offset=-199,time_unit=100,samples_per_pixel=25,numerator=2,denominator=3,group_factor=4,working_count=1000,group_count=100,ring_trigger=50,ring_length=200)
        self.assertEqual(p['integer_offset_pixels'],-1)
        self.assertEqual(p['sample_shift'],0) # two truncating divides, not offset*ratio
        self.assertEqual(p['read_start_before_padding'],200)
    def test_buffer_address_correspondence(self):
        # Independent byte addresses from the firmware's pointer expression.
        base=0x42c62af4;working=1000;saved=800;c1=-12;c2=7;j=530
        initial=base+((51000-working)&~1)
        final=base+((51000-saved)&~1)+2*c1+2*c2
        expected=(initial+2*j-final)//2
        self.assertEqual(retained_address_index(j,working,saved,c1,c2),expected)
        with self.assertRaises(ValueError):retained_address_index(j,working,saved,c1,None)
    def test_forward_filter_is_left_anchored_and_preserves_tail(self):
        self.assertEqual(forward_average_interior([0,0,12,0,0],3),[4,4,4,0,0])
        self.assertEqual(forward_average_interior([0,0,0,12,12],3),[0,4,8,12,12])
    def test_reference_saved_positions(self):
        from pathlib import Path
        for path in (Path(__file__).parent/'fixtures/reference').glob('*.wav'):
            with self.subTest(file=path.name):
                d=path.read_bytes();u=lambda o,n=4:int.from_bytes(d[o:o+n],'big')
                p=acquisition_positions(offset=int.from_bytes(d[0x1c8:0x1d0],'big',signed=True),time_unit=u(0x1af,8),samples_per_pixel=u(0x1c0),numerator=u(0x16e),denominator=u(0x172),group_factor=u(0xdb,1),working_count=u(0x124),group_count=u(0x12c),ring_trigger=u(0x10f),ring_length=u(0x134))
                self.assertEqual(p['working_trigger_search_index'],u(0x115))
                self.assertEqual(p['read_start_before_padding'],u(0x20f))
