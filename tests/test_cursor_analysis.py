import unittest
from decoder.cursor_analysis import x_selection,y_selection
class CursorTests(unittest.TestCase):
    def test_reversed_inclusive_time_interval(self):
        values=[9,1,2,3,8];m=x_selection(values,3,1,.001)
        self.assertEqual((m['minimum'],m['maximum'],m['mean'],m['count']),(1,3,2,3))
        self.assertEqual(m['delta_s'],-.002);self.assertEqual(m['one_cycle_hz'],500)
        self.assertEqual(values,[9,1,2,3,8])
    def test_coincident_and_missing_timing(self):
        self.assertIsNone(x_selection([2,4],1,1,.01)['one_cycle_hz'])
        self.assertIsNone(x_selection([2,4],0,1)['one_cycle_hz'])
    def test_bounds_and_empty(self):
        self.assertEqual(x_selection([2,4],-20,40,.1)['count'],2)
        self.assertEqual(x_selection([],0,1,.1)['count'],0)
    def test_voltage_band_inclusive_reversed(self):
        m=y_selection([-3,-2,-1,0,1],0,-2)
        self.assertEqual((m['minimum'],m['maximum'],m['mean'],m['count']),(-2,0,-1,3))
        self.assertEqual(y_selection([1,2],4,5)['count'],0)
if __name__=='__main__':unittest.main()
