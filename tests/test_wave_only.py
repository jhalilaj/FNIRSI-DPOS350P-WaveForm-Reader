from pathlib import Path
import unittest
from decoder.fnirsi_decode import decode,channel_samples
from decoder.calibration import volts


class WaveOnlyTests(unittest.TestCase):
    def test_blanking_embedded_preview_does_not_change_values_or_timing(self):
        data=(Path(__file__).parent/'fixtures/reference/7.wav').read_bytes()
        original,samples=decode(data)
        section=original['sections'][1]
        modified=bytearray(data)
        start=section['offset']+4;end=section['offset']+section['length']
        modified[start:end]=bytes(end-start)
        other,other_samples=decode(modified)
        self.assertEqual(samples,other_samples)
        self.assertEqual(volts(original,channel_samples(original,samples)),volts(other,channel_samples(other,other_samples)))
        self.assertEqual(original['calibration'],other['calibration'])


if __name__=='__main__':unittest.main()
