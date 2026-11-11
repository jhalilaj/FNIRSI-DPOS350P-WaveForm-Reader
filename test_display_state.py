from pathlib import Path
import copy,unittest
from fnirsi_decode import decode
from display_state import fields,clipped_view
class SavedDisplayTests(unittest.TestCase):
    def capture(self,name='7'):
        d=bytearray((Path(__file__).parent/'examples/reference'/f'{name}.wav').read_bytes())
        m,_=decode(d);return d,m
    def test_variable_frame_table_and_disabled_visibility(self):
        for name in ('1','3','7'):
            d,m=self.capture(name);s=m['saved_display']
            self.assertEqual(s['cursor_block_offset'],0x26a+12*s['frame_count'])
            self.assertEqual(s['x_pixels'],[190,760]);self.assertFalse(s['x_enabled']);self.assertFalse(s['y_enabled'])
    def test_zoom_and_pan_mapping_use_retained_geometry(self):
        d,m=self.capture();d[0x17e:0x186]=(0).to_bytes(8,'big')
        d[0x1c8:0x1d0]=(0).to_bytes(8,'big')
        capture=int.from_bytes(d[0x1af:0x1b7],'big')
        d[0x190:0x198]=(capture//2).to_bytes(8,'big')
        s=fields(d,m);per=m['calibration']['samples_per_pixel_candidate']
        self.assertEqual(s['viewport_samples'],[237.5*per,712.5*per])
        d[0x17e:0x186]=(-10*capture).to_bytes(8,'big',signed=True)
        shifted=fields(d,m)
        self.assertEqual(shifted['viewport_samples'][0]-s['viewport_samples'][0],10*per)
    def test_cursor_flags_and_channel_specific_y_voltage(self):
        d,m=self.capture();o=m['saved_display']['cursor_block_offset'];d[o+2:o+4]=bytes([1,1])
        s=fields(d,m);self.assertTrue(s['x_enabled']);self.assertTrue(s['y_enabled'])
        for name,info in m['calibration']['channels'].items():
            expected=(503-2-info['display_zero_position']-125)*info['display_volts_per_div']/63
            self.assertEqual(s['y_volts_by_channel'][name][0],expected)
    def test_preview_independence(self):
        d,m=self.capture();section=m['sections'][1];start=section['offset'];end=start+section['length']
        d[start:end]=bytes(end-start)
        self.assertEqual(fields(d,m),m['saved_display'])
    def test_cursor_read_cannot_cross_settings_boundary(self):
        d,m=self.capture();m=copy.deepcopy(m)
        m['sections'][0]['length']=0x26a+12*m['saved_display']['frame_count']-50+10
        self.assertNotIn('x_pixels',fields(d,m))
    def test_clipping_rejects_off_record_view(self):
        self.assertEqual(clipped_view({'viewport_samples':[-10,500]},100),(0.,99.))
        for view in ([200,300],[10,10],[float('nan'),5]):
            with self.assertRaises(ValueError):clipped_view({'viewport_samples':view},100)

