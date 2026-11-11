import struct
import unittest
from fnirsi_decode import decode, channel_samples, extract_preview


def fixture(samples=(0, 1, 32768, 65535)):
    settings, preview = b'abc', b'12345'
    payload = struct.pack(f'>{len(samples)}H', *samples)
    header = struct.pack('>7I', 50, 3, 53, 5, 58, len(payload), 58 + len(payload))
    return header + bytes(50 - len(header)) + settings + preview + payload


class DecoderTests(unittest.TestCase):
    def test_variable_section_offsets_and_unsigned_endpoints(self):
        meta, samples = decode(fixture())
        self.assertEqual(samples, [0, 1, 32768, 65535])
        self.assertEqual(meta['sections'][2]['offset'], 58)
        self.assertIsNone(meta['sample_rate_hz'])

    def test_truncation_and_extra_data(self):
        for data in (fixture()[:-1], fixture() + b'x'):
            with self.assertRaises(ValueError):
                decode(data)

    def test_corrupt_directory(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, 8, 54)
        with self.assertRaises(ValueError):
            decode(data)

    def test_unsupported_inputs(self):
        for data in (b'', b'RIFF' + bytes(100)):
            with self.assertRaises(ValueError):
                decode(data)


class LayoutTests(unittest.TestCase):
    def test_two_channels_are_not_concatenated(self):
        self.assertEqual(channel_samples({'channel_flag_bytes': [1, 1]}, [10,20,30,40]),
                         {'CH1': [10,20], 'CH2': [30,40]})

    def test_single_channel_uses_entire_block(self):
        self.assertEqual(channel_samples({'channel_flag_bytes': [1, 0]}, [10,20,30,40]),
                         {'CH1': [10,20,30,40]})

    def test_odd_dual_channel_block_is_rejected(self):
        with self.assertRaises(ValueError):
            channel_samples({'channel_flag_bytes':[1,1]}, [1,2,3])

    def test_rgb565_preview(self):
        data=struct.pack('>HHHHH',3,1,0xf800,0x07e0,0x001f)
        meta={'sections':[{}, {'offset':0,'length':len(data)}]}
        self.assertEqual(extract_preview(data,meta), (3,1,bytes([255,0,0,0,255,0,0,0,255])))

    def test_preview_dimension_mismatch(self):
        data=struct.pack('>HHH',3,1,0xf800)
        with self.assertRaises(ValueError):
            extract_preview(data,{'sections':[{}, {'offset':0,'length':len(data)}]})


class CalibrationTests(unittest.TestCase):
    def fixture(self, end=891):
        from calibration import fields
        data=bytearray(end)
        def put(offset,value,size=8):data[offset:offset+size]=value.to_bytes(size,'big',signed=True)
        put(0x4a,95,2);put(0x4e,63,2);put(0xe4,64,4)
        put(0x6d,1000000);put(0x75,2000000);put(0x81,10,4)
        put(0x190,500000000);put(0x1af,1000000000);put(0x1c0,50,4)
        base=end-240
        for i,value in enumerate((2000000,0,1000000,1100000,2000000,2000000)):
            put(base+i*8,value)
        meta={'sections':[{'offset':50,'length':end-50}]}
        channels={'CH1':[672,4704]}
        meta['calibration']=fields(data,meta,channels)
        return data,meta,channels

    def test_capture_scale_not_display_scale(self):
        from calibration import volts
        _,meta,channels=self.fixture()
        self.assertEqual(volts(meta,channels),{'CH1':[0.0,2.0]})
        self.assertEqual(meta['calibration']['display_seconds_per_div'],.0005)
        self.assertEqual(meta['calibration']['capture_seconds_per_div'],.001)
        self.assertAlmostEqual(meta['calibration']['sample_interval_s_candidate'],.001/(95*50))

    def test_variable_measurement_trailer(self):
        from calibration import volts
        _,meta,channels=self.fixture(end=915)
        self.assertEqual(volts(meta,channels)['CH1'],[0.0,2.0])

    def test_conflicting_readout_refuses_conversion(self):
        from calibration import fields,volts
        data,meta,channels=self.fixture()
        data[651:659]=(9000000).to_bytes(8,'big')
        meta['calibration']=fields(data,meta,channels)
        with self.assertRaises(ValueError):volts(meta,channels)

    def test_small_extrema_difference_is_warned_not_hidden(self):
        from calibration import fields,volts
        data,meta,channels=self.fixture()
        data[651:659]=(2080000).to_bytes(8,'big')
        meta['calibration']=fields(data,meta,channels)
        self.assertFalse(meta['calibration']['channels']['CH1']['strict_extrema_agreement'])
        self.assertTrue(meta['calibration']['channels']['CH1']['conversion_usable'])
        self.assertEqual(volts(meta,channels)['CH1'],[0.0,2.0])

    def test_uses_saved_geometry_instead_of_constants(self):
        from calibration import fields
        data,meta,channels=self.fixture()
        data[0x4a:0x4c]=(100).to_bytes(2,'big')
        data[0x4e:0x50]=(64).to_bytes(2,'big')
        data[0xe4:0xe8]=(128).to_bytes(4,'big')
        result=fields(data,meta,channels)
        self.assertAlmostEqual(result['sample_interval_s_candidate'],.001/(100*50))
        self.assertEqual(result['channels']['CH1']['candidate_zero_raw'],1344)
        self.assertEqual(result['channels']['CH1']['candidate_volts_per_count'],2/(128*64))

    def test_invalid_geometry_disables_calibration(self):
        from calibration import fields,volts
        data,meta,channels=self.fixture()
        data[0x4a:0x4c]=bytes(2)
        meta['calibration']=fields(data,meta,channels)
        with self.assertRaises(ValueError):volts(meta,channels)

    def test_unknown_calibration_refuses_conversion(self):
        from calibration import volts
        with self.assertRaises(ValueError):volts({}, {'CH1':[1,2]})


class TimingTests(unittest.TestCase):
    def data(self):
        d=bytearray(0x200)
        def put(o,v):d[o:o+8]=v.to_bytes(8,'big',signed=True)
        put(0x190,1000000000);put(0x1af,2000000000)
        put(0x17e,-10000000000);put(0x1c8,40000000000)
        return d

    def test_uses_retained_marker_not_display_marker(self):
        from timing import trigger_fields
        f=trigger_fields(self.data(),{'samples_per_pixel_candidate':25},23752)
        self.assertEqual(f['display_marker_pixel'],465)
        self.assertEqual(f['sample_index_candidate'],495*25)

    def test_offscreen_marker_not_forced_into_capture(self):
        from timing import trigger_fields
        self.assertIsNone(trigger_fields(self.data(),{'samples_per_pixel_candidate':25},100)['sample_index_candidate'])

    def test_unavailable_marker_fails_explicitly(self):
        from timing import origin_sample
        with self.assertRaises(ValueError):origin_sample({},'trigger marker')
        self.assertEqual(origin_sample({}),0.)


class FirmwareCountTests(unittest.TestCase):
    def capture(self,flags=(1,1),declared=2):
        settings=bytearray(300)
        settings[0x65-50]=flags[0];settings[0xa6-50]=flags[1]
        struct.pack_into('>I',settings,0x120-50,declared)
        payload=struct.pack('>4H',1,2,3,4)
        return struct.pack('>7I',50,300,350,0,350,len(payload),358)+bytes(22)+settings+payload

    def test_declared_count_matches_dual_channel_payload(self):
        m,a=decode(self.capture())
        self.assertEqual(m['declared_samples_per_channel'],2)
        self.assertEqual(channel_samples(m,a),{'CH1':[1,2],'CH2':[3,4]})

    def test_inconsistent_counts_and_flags_rejected(self):
        for data in (self.capture(declared=3),self.capture(declared=0),self.capture(flags=(2,0))):
            with self.assertRaises(ValueError):decode(data)


if __name__ == '__main__':
    unittest.main()

