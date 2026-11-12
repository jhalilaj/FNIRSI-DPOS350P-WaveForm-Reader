import unittest
from pathlib import Path
from types import SimpleNamespace
from exports.report_export import build_report
from decoder.fnirsi_decode import decode
class ExportReportTests(unittest.TestCase):
    def test_report_visible_interval_and_provenance(self):
        var=lambda value:SimpleNamespace(get=lambda:value)
        v=SimpleNamespace(start=1.,end=3.,n=5,channels={'CH1':[99,1,2,3,99],'CH2':[8]*5},visible={'CH1':var(True),'CH2':var(False)},meta={'calibration':{},'sha256':'test'},filename=Path('capture.wav'),units='raw',time_origin='first sample',scope_layout=True,display_positions={'CH1':200},delta_cursors=[1,3],y_cursors=None,y_channel=var('CH1'),cursor_readout=var('test cursors'))
        r=build_report(v)
        self.assertEqual(r['visible_sample_measurements']['CH1']['mean'],2)
        self.assertNotIn('CH2',r['visible_sample_measurements'])
        self.assertEqual(r['view']['sample_end_exclusive'],4)
        self.assertEqual(r['metadata']['sha256'],'test')
        r['metadata']['sha256']='changed';r['view']['x_cursor_samples'][0]=0
        self.assertEqual(v.meta['sha256'],'test');self.assertEqual(v.delta_cursors,[1,3])
    def test_bmp_is_not_treated_as_waveform(self):
        with self.assertRaisesRegex(ValueError,'BMP screenshot'):decode(b'BM'+bytes(100))
