"""Timing for saved 5/10 samples-per-pixel acquisition settings."""
import unittest
from pathlib import Path
from decoder.fnirsi_decode import decode
from decoder.cursor_analysis import x_selection

class FastCaptureTimingTests(unittest.TestCase):
    def test_fast_saved_timebases_provide_time_and_cursor_frequency(self):
        original=(Path(__file__).parent/'fixtures/reference/7.wav').read_bytes()
        for density,time_ps in ((5,1000000),(10,2000000),(20,4000000),(25,5000000),(50,10000000)):
            with self.subTest(density=density):
                data=bytearray(original)
                data[0x1C0:0x1C4]=density.to_bytes(4,'big')
                data[0x1AF:0x1B7]=time_ps.to_bytes(8,'big')
                data[0x190:0x198]=time_ps.to_bytes(8,'big')
                width = 950
                group = data[0xDB]
                count = (width * density // group + 1) * group
                start = int.from_bytes(data[16:20], 'big')
                data = data[:start] + bytes(4 * count)
                data[20:24] = (4 * count).to_bytes(4, 'big')
                data[24:28] = len(data).to_bytes(4, 'big')
                data[0x120:0x124] = count.to_bytes(4, 'big')
                meta,_=decode(data)
                dt=meta['calibration']['sample_interval_s_candidate']
                self.assertAlmostEqual(dt,time_ps/1e12/(95*density))
                result=x_selection([0]*2000,0,950,dt)
                self.assertAlmostEqual(result['delta_s'],950*dt)
                self.assertAlmostEqual(result['one_cycle_hz'],1/(950*dt))
                self.assertTrue(meta['calibration']['trigger'])
                data[0x4E:0x50] = (62).to_bytes(2, 'big')
                raw_meta, _ = decode(data)
                self.assertAlmostEqual(raw_meta['calibration']['sample_interval_s_candidate'], dt)
                data[0x1C0:0x1C4] = (density + 1).to_bytes(4, 'big')
                invalid_meta, _ = decode(data)
                self.assertIsNone(invalid_meta['calibration']['sample_interval_s_candidate'])
