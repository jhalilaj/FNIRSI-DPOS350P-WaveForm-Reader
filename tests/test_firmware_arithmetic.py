import unittest
from decoder.firmware_arithmetic import signed_divide,coordinate_readout_microvolts

class FirmwareArithmeticTests(unittest.TestCase):
    def test_signed_division_truncates_toward_zero(self):
        for a,b,expected in [(-5,2,-2),(5,-2,-2),(-5,-2,2),(5,2,2)]:
            self.assertEqual(signed_divide(a,b),expected)

    def test_zero_reference_and_quantization(self):
        self.assertEqual(coordinate_readout_microvolts(125*64,125,2000000),0)
        self.assertEqual(coordinate_readout_microvolts(125*64+63,125,2000000),0)
        self.assertEqual(coordinate_readout_microvolts(124*64,125,2000000),-31746)

    def test_one_division_and_geometry(self):
        self.assertEqual(coordinate_readout_microvolts((125+63)*64,125,2000000),2000000)
        self.assertEqual(coordinate_readout_microvolts((10+64)*128,10,1000000,128,64),1000000)

    def test_invalid_input(self):
        for word in [-1,65536]:
            with self.assertRaises(ValueError):coordinate_readout_microvolts(word,0,1)
        with self.assertRaises(ValueError):signed_divide(1,0)
