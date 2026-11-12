"""Scope-marker-based timing. Marker origin is not a calibrated trigger instant."""
def trigger_fields(data, calibration, sample_count):
    if len(data)<0x1D0:return {}
    integer=lambda offset:int.from_bytes(data[offset:offset+8],'big',signed=True)
    display=integer(0x190);capture=integer(0x1AF)
    per_pixel=calibration.get('samples_per_pixel_candidate')
    if display<=0 or capture<=0 or per_pixel not in (25,50):return {}
    from decoder.firmware_arithmetic import signed_divide
    width=int.from_bytes(data[0x36:0x38],'big') or 950
    center=width//2
    display_offset=integer(0x17E);capture_offset=integer(0x1C8)
    display_pixel=center+signed_divide(display_offset,display)
    capture_pixel=center+capture_offset/capture
    index=capture_pixel*per_pixel
    return {'display_marker_pixel':display_pixel,'capture_marker_pixel':capture_pixel,
            'sample_index_candidate':index if 0<=index<sample_count else None,
            "display_marker_fractional_pixel":center+display_offset/display,
            "capture_marker_integer_pixel":center+signed_divide(capture_offset,capture),
            "display_offset_ps":display_offset,"capture_offset_ps":capture_offset,
            "display_time_unit_ps":display,"capture_time_unit_ps":capture,
            "plot_width_pixels":width,
            "trigger_enabled_raw":data[0xF9],"trigger_gate_raw":data[0xF8],
            "trigger_channel_raw":data[0x100],"trigger_edge_raw":data[0xFF],
            "trigger_level_coordinate_raw":int.from_bytes(data[0x101:0x103],'big',signed=True),
            "primary_alignment_correction_samples":int.from_bytes(data[0x113:0x115],'big',signed=True),
            "secondary_alignment_correction_samples":None,
            "trigger_ring_position_raw":int.from_bytes(data[0x10F:0x113],'big'),
            "ring_length_raw":int.from_bytes(data[0x134:0x138],'big'),
            "hardware_trigger_sample_index":None,
            "origin_kind":"retained marker model",
            'status':'firmware integer display marker; retained fractional origin is a model; runtime edge correction is not serialized' }


def origin_sample(metadata, mode='first sample'):
    if mode=='trigger marker':
        value=metadata.get('calibration',{}).get('trigger',{}).get('sample_index_candidate')
        if value is None:raise ValueError('Trigger marker is outside this capture or its encoding is unknown')
        return value
    return 0.
