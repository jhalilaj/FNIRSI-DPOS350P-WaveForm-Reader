import unittest
from pathlib import Path
from measurements import analyze
from fnirsi_decode import decode
class PulseMeasurementsTests(unittest.TestCase):
    def test_square_pulse_widths(self):
        m=analyze(([0.]*6+[5.]*4)*10,.0001)
        self.assertAlmostEqual(m['positive_width_s'],.0004)
        self.assertAlmostEqual(m['negative_width_s'],.0006)
        self.assertIsNone(m['rise_time_s']);self.assertIsNone(m['fall_time_s'])
    def test_resolved_ramp_edges_and_single_edge(self):
        pulse=[0.]*30+list(range(11))+[10.]*30+list(range(10,-1,-1))+[0.]*30
        m=analyze(pulse,.001)
        self.assertAlmostEqual(m['rise_time_s'],.008)
        self.assertAlmostEqual(m['fall_time_s'],.008)
        self.assertIsNone(m['frequency_hz'])
        self.assertIsNone(m['positive_width_s'])
    def test_no_timing_no_edge_seconds(self):
        m=analyze(list(range(100)))
        self.assertIsNone(m['rise_time_s']);self.assertIsNone(m['positive_width_s'])
    def test_stored_timing_units(self):
        p=Path(__file__).parent/'examples/reference/3.wav';d=p.read_bytes();m,_=decode(d)
        r=m['calibration']['channels']['CH1']['stored_readouts']
        self.assertEqual(r['frequency_hz'],1000.276)
        self.assertEqual(r['period_s'],.000999723680)
        self.assertEqual(r['positive_duty_percent'],49.99)
        self.assertAlmostEqual(r['positive_width_s']+r['negative_width_s'],r['period_s'])
    def test_glitches_do_not_produce_unambiguous_width(self):
        values=([0.]*20+[10.]*10+[0.]+[10.]*10+[0.]*20)*5
        # A step within an otherwise high pulse creates extra crossings.
        m=analyze(values,.001)
        self.assertIsNone(m['frequency_hz']);self.assertIsNone(m['positive_width_s'])
