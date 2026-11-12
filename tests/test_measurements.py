import math,unittest
from decoder.measurements import analyze


class MeasurementsTests(unittest.TestCase):
    def test_constant_has_rms_but_no_frequency(self):
        m=analyze([3.]*100,.001)
        self.assertEqual(m['rms'],3);self.assertEqual(m['ac_rms'],0)
        self.assertIsNone(m['frequency_hz'])

    def test_square_frequency_period_duty_and_rms(self):
        m=analyze(([0.]*6+[5.]*4)*10,.0001)
        self.assertAlmostEqual(m['frequency_hz'],1000)
        self.assertAlmostEqual(m['period_s'],.001)
        self.assertAlmostEqual(m['duty_percent'],40)
        self.assertAlmostEqual(m['rms'],math.sqrt(10))

    def test_sine_rms_and_frequency(self):
        m=analyze([2*math.sin(2*math.pi*50*i/1000) for i in range(1000)],.001)
        self.assertAlmostEqual(m['frequency_hz'],50,places=5)
        self.assertAlmostEqual(m['rms'],math.sqrt(2),places=5)

    def test_step_is_not_a_periodic_waveform(self):
        self.assertIsNone(analyze([0.]*50+[1.]*50,.001)['frequency_hz'])

    def test_without_timebase_does_not_report_hz(self):
        self.assertIsNone(analyze(([0.]*6+[5.]*4)*10)['frequency_hz'])


if __name__=='__main__':unittest.main()
