import unittest,copy
from pathlib import Path
from fnirsi_decode import decode
from scope_controls import trigger_info,measurement_text
class ScopeControlsTests(unittest.TestCase):
    def capture(self,n='7'):
        return decode((Path(__file__).parent/'examples/reference'/f'{n}.wav').read_bytes())[0]
    def test_signed_scope_selection_preserves_channel_and_order(self):
        self.assertEqual(self.capture('3')['saved_measurement_selection']['entries'],[('CH1','max'),('CH1','min'),('CH1','avg'),('CH1','freq')])
        self.assertEqual(self.capture('7')['saved_measurement_selection']['entries'],[('CH2','max'),('CH2','min'),('CH2','avg'),('CH2','freq')])
    def test_trigger_uses_selected_channels_current_scale(self):
        m=self.capture();t=trigger_info(m);i=m['calibration']['channels']['CH2']
        self.assertEqual(t['channel'],'CH2');self.assertEqual(t['edge'],'Rising')
        expected=(190-i['display_zero_position'])*i['display_volts_per_div']/63
        self.assertEqual(t['level_v'],expected)
        m['calibration']['channels']['CH1']['display_zero_position']+=100
        self.assertEqual(trigger_info(m)['level_v'],expected)
    def test_unknown_and_conflicting_calibration_have_no_physical_level(self):
        self.assertIsNone(trigger_info({})['level_v'])
        m=self.capture();m['calibration']['channels']['CH2']['conversion_usable']=False
        self.assertIsNone(trigger_info(m)['level_v'])
    def test_unknown_edge_is_not_falsely_labelled_falling(self):
        m=self.capture();m['calibration']['trigger']['trigger_edge_raw']=7
        self.assertEqual(trigger_info(m)['edge'],'Unknown edge')
    def test_measurement_format_handles_signed_peak_and_unavailable(self):
        m={'maximum':2,'minimum':-3,'duty_percent':None}
        self.assertIn('-3 V',measurement_text('peak',m,'V'))
        self.assertIn('—',measurement_text('duty-',m,'V'))
        m['duty_percent']=35
        self.assertIn('65 %',measurement_text('duty-',m,'V'))
