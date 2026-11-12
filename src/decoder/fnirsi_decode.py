"""Experimental DPOS350P section parser. No automatic physical calibration."""
import hashlib
import struct


def decode(data):
    if len(data) < 50:
        raise ValueError('File is too short for the observed 50-byte directory')
    if data[:2] == b'BM':
        raise ValueError('This is a BMP screenshot, not waveform sample data. Open the scope waveform WAV file.')
    if data[:4] == b'RIFF':
        raise ValueError('This is an audio WAV, not the observed FNIRSI format')
    start, size, preview_start, preview_size, samples_start, samples_size, total = struct.unpack_from('>7I', data)
    if start != 50 or start + size != preview_start or preview_start + preview_size != samples_start:
        raise ValueError('Unsupported or inconsistent section directory')
    if samples_start + samples_size != total or total != len(data):
        raise ValueError('Section lengths do not match the file length (possibly truncated)')
    if samples_size == 0 or samples_size % 2:
        raise ValueError('Sample block must contain a nonzero even number of bytes')
    samples = list(struct.unpack_from(f'>{samples_size // 2}H', data, samples_start))
    metadata = {
        'status': 'experimental; section structure checked on 24 captures; model checked against supplied 1X references',
        'sha256': hashlib.sha256(data).hexdigest(),
        'file_bytes': len(data),
        'sections': [
            {'name': 'settings_candidate', 'offset': start, 'length': size},
            {'name': 'preview_candidate', 'offset': preview_start, 'length': preview_size},
            {'name': 'sample_candidate', 'offset': samples_start, 'length': samples_size},
        ],
        'sample_encoding': '16-bit big-endian words (firmware-confirmed serialization)',
        'sample_representation': 'retained waveform coordinate words; not established as untouched hardware ADC codes',
        'sample_processing_basis': 'firmware working-window copy to serializer buffers identified; processing depends on acquisition mode',
        'sample_count': len(samples), 'raw_min': min(samples), 'raw_max': max(samples),
        'channel': None, 'sample_rate_hz': None, 'volts_per_count': None,
        'trigger_sample': None,
        'warnings': ['Channel identity and channel packing unverified',
                     'Physical calibration unverified; opt-in inferred conversion may be available; raw values are not volts',
                     'Embedded preview is RGB565; it is a screenshot, not calibrated sample data'],
    }
    if start + size >= 0xAA:
        enabled = [data[0x65], data[0xA6]]
        metadata['channel_enabled_candidates'] = {'CH1': bool(enabled[0]), 'CH2': bool(enabled[1])}
        metadata['channel_flag_bytes'] = enabled
        metadata['scale_index_candidates'] = {'CH1': data[0x68], 'CH2': data[0xA9]}
        metadata['timebase_index_candidate'] = data[0x18F] if start + size > 0x18F else None
        if enabled == [1, 1] and len(samples) % 2 == 0:
            metadata['layout'] = 'CH1 block followed by CH2 block (firmware-confirmed)'
            metadata['samples_per_channel'] = len(samples) // 2
        elif enabled in ([1, 0], [0, 1]):
            metadata['layout'] = 'single enabled channel, full sample block (firmware-confirmed)'
            metadata['samples_per_channel'] = len(samples)
        else:
            metadata['layout'] = 'unknown'
        if start + size >= 0x124:
            declared = struct.unpack_from('>I', data, 0x120)[0]
            if enabled not in ([1,0],[0,1],[1,1]):
                raise ValueError('Unsupported channel enable flags')
            if declared == 0 or samples_size != 2*declared*sum(enabled):
                raise ValueError('Firmware sample count does not match channel payload length')
            metadata['declared_samples_per_channel'] = declared
            metadata['layout_basis'] = 'Firmware serializer 0x400455E4 and big-endian codec 0x40067160'
        metadata['warnings'][0] = 'Channel packing checked on 17 original and 7 reference files, including CH2-only'
    from decoder.compatibility import assess
    metadata['compatibility'] = assess(data,metadata)
    from decoder.acquisition import fields as acquisition_fields
    metadata['acquisition'] = acquisition_fields(data,metadata) if metadata['compatibility']['settings_layout_matched'] else {'status':'unavailable: unrecognized settings layout'}
    if metadata['compatibility']['numeric_model_allowed']:
        from decoder.calibration import fields
        metadata['calibration'] = fields(data, metadata, channel_samples(metadata, samples))
        from decoder.timing import trigger_fields
        metadata['calibration']['trigger'] = trigger_fields(data, metadata['calibration'], metadata.get('samples_per_channel',len(samples)))
        from decoder.display_state import fields as display_fields
        metadata['saved_display'] = display_fields(data,metadata)
    else:
        metadata['calibration']={'status':'unavailable: settings layout or coordinate geometry is outside inspected compatibility profile'}
        metadata['saved_display']={'status':'unavailable: compatibility profile mismatch'}
        metadata['warnings'].append(metadata['compatibility']['status'])
    from decoder.scope_controls import saved_selection
    metadata['saved_measurement_selection'] = saved_selection(data,metadata)
    return metadata, samples


def channel_samples(metadata, samples):
    flags = metadata.get('channel_flag_bytes')
    if flags == [1, 1]:
        if len(samples) % 2:
            raise ValueError('Dual-channel block cannot be split into equal channels')
        mid = len(samples) // 2
        return {'CH1': samples[:mid], 'CH2': samples[mid:]}
    if flags in ([1, 0], [0, 1]):
        return {'CH1' if flags[0] else 'CH2': samples}
    return {'RAW': samples}


def extract_preview(data, metadata):
    # 203 x 138 RGB565 image in all 17 captures. Exact length is checked.
    section = metadata['sections'][1]
    offset, length = section['offset'], section['length']
    if length < 4:
        raise ValueError('Preview is too short')
    width, height = struct.unpack_from('>HH', data, offset)
    if not width or not height or length != 4 + width * height * 2:
        raise ValueError('Unsupported preview dimensions or length')
    rgb = bytearray()
    for (v,) in struct.iter_unpack('>H', data[offset + 4:offset + length]):
        rgb.extend((((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31))
    return width, height, bytes(rgb)
