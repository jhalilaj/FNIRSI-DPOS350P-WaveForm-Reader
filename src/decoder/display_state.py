"""Saved display/cursor geometry decoded from WAV settings, independently of preview."""
import math

def fields(data,metadata):
    sections=metadata.get('sections',[])
    if not sections:return {}
    end=sections[0]['offset']+sections[0]['length']
    if end>len(data) or end<0x26A:return {'status':'saved display settings unavailable'}
    def u(at,size=4,signed=False):return int.from_bytes(data[at:at+size],'big',signed=signed)
    frames=u(0x1A4,2);cursor=0x26A+12*frames
    if frames>50 or cursor+21>end:return {'status':'unsupported frame table or truncated cursor settings'}
    width=u(0x36,2);height=u(0x38,2);horizontal=u(0x4A,2);vertical=u(0x4E,2)
    current=u(0x190,8);retained=u(0x1AF,8);per_pixel=u(0x1C0)
    if min(width,height,horizontal,vertical,current,retained,per_pixel)<=0:return {'status':'invalid saved display geometry'}
    display_offset=u(0x17E,8,True);capture_offset=u(0x1C8,8,True)
    center=width//2;ratio=current/retained
    def sample(pixel):return (center+(capture_offset-display_offset)/retained+(pixel-center)*ratio)*per_pixel
    x=[u(cursor+i,4,True) for i in (5,9)];y=[u(cursor+i,4,True) for i in (13,17)]
    flags=[u(cursor+i,1) for i in range(5)]
    values={}
    for name,info in metadata.get('calibration',{}).get('channels',{}).items():
        gain=info.get('display_volts_per_div');zero=info.get('display_zero_position')
        if gain and zero is not None:values[name]=[(height-2-zero-p)*gain/vertical for p in y]
    return {'status':'saved display model; enabled cursor restoration not yet checked on hardware capture',
            'frame_count':frames,'cursor_block_offset':cursor,
            'cursor_flags_raw':flags,'x_enabled':bool(flags[2]),'y_enabled':bool(flags[3]),
            'x_pixels':x,'y_pixels':y,'x_samples':[sample(p) for p in x],
            'y_volts_by_channel':values,
            'viewport_samples':[sample(0),sample(width)],
            'basis':'serializer 0x400448B4 variable frame table; cursor drawing 0x4003117C; cursor arithmetic 0x40031794; retained/display offset mapping'}

def clipped_view(state,sample_count):
    start,end=state.get('viewport_samples',[math.nan,math.nan])
    if sample_count<2 or not all(math.isfinite(v) for v in (start,end)) or start>=end:
        raise ValueError('Saved viewport is unavailable or invalid')
    start=max(0.,start);end=min(float(sample_count-1),end)
    if end-start<1:raise ValueError('Saved viewport lies outside this capture or spans fewer than two samples')
    return start,end
