"""Saved acquisition diagnostics; never reprocess retained waveform samples."""
def fields(data,metadata):
    sections=metadata.get('sections',[])
    if not sections or sections[0]['offset']!=50:return {}
    end=sections[0]['offset']+sections[0]['length']
    if end<0x21E:return {'status':'settings too short for mapped acquisition diagnostics'}
    def u(offset,size=1):return int.from_bytes(data[offset:offset+size],'big')
    flags=metadata.get('channel_flag_bytes',[])
    expected={(1,1):0,(1,0):1,(0,1):2}.get(tuple(flags))
    mode=u(0xA5)
    consistent=expected is not None and mode==expected
    return {
        'status':'mapped saved controls; acquisition history incomplete',
        'channel_path_raw':mode,
        'channel_path':{0:'dual-channel / four input lanes per channel',1:'CH1 only / eight input lanes',2:'CH2 only / eight input lanes'}.get(mode,'unknown'),
        'channel_path_matches_enabled_channels':consistent,
        'input_lanes_per_channel':(4 if mode==0 else 8) if consistent else None,
        'enabled_channel_count_raw':u(0xDA),'lane_group_factor_raw':u(0xDB),
        'sample_shift_raw':u(0xE8,4),
        'trigger_mode_raw':u(0xFE),
        'averaging_control_raw':u(0x21D),
        'moving_average_window':None,
        'pair_smoothing_enabled':None,
        'unsaved_processing_state':['moving average window (state+0x662)','pair smoothing enable (state+0x70D)'],
        'processing_policy':'decode retained coordinates unchanged; do not repeat firmware filtering',
        'basis':'0x4003A908 channel path selection; 0x4004073C input-lane coordinate conversion; 0x400413C8 processing sequence; settings-prefix-map.tsv serializer mapping',
    }
