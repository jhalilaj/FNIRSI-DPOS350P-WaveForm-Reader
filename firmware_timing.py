"""Static firmware timing equations for investigation, not a hardware timestamp API.

All inputs must belong to the same acquisition. Results are address/index models;
filter delay and peripheral trigger phase are deliberately not inferred here.
"""
from firmware_arithmetic import signed_divide

def acquisition_positions(*,offset,time_unit,samples_per_pixel,numerator,denominator,
                          group_factor,working_count,group_count,ring_trigger,ring_length):
    if min(time_unit,samples_per_pixel,numerator,denominator,group_factor,
           working_count,group_count,ring_length)<=0:
        raise ValueError('Positive acquisition geometry and timing required')
    pixels=signed_divide(offset,time_unit)
    offset_steps=signed_divide(pixels,denominator)
    shift=samples_per_pixel*numerator*offset_steps
    group_shift=signed_divide(shift,group_factor)
    start=ring_trigger-signed_divide(group_count,2)-group_shift
    # Firmware adds ring_length until strictly positive. It does not modulo
    # a positive start here; the later peripheral read-start write does that.
    if start<=0:start+=((1-start+ring_length-1)//ring_length)*ring_length
    return {'integer_offset_pixels':pixels,'sample_shift':shift,
            'working_trigger_search_index':working_count//2+shift,
            'read_start_before_padding':start}

def retained_address_index(working_index,working_count,saved_count,primary,secondary):
    """Follow the selected working address into a standard single-frame copy.

    Requires known corrections and the unexpanded 0x400413C8 path. This does
    not undo filtering or recover the hardware's within-group trigger phase.
    """
    if secondary is None:raise ValueError('Secondary alignment correction was not saved')
    if not 0<working_count<=51000 or not 0<saved_count<=working_count:
        raise ValueError('Unsupported working/saved geometry')
    initial=(51000-working_count)//2
    final=(51000-saved_count)//2+primary+secondary
    return working_index-(final-initial)

def forward_average_interior(values,window):
    """0x40040F18 interior: output j uses input j..j+window-1; tail untouched."""
    if not 1<=window<=len(values):raise ValueError('Window outside supplied buffer')
    if any(not 0<=v<=65535 for v in values):raise ValueError('Expected unsigned coordinate words')
    if window*max(values)>=2**31:raise ValueError('Signed accumulator overflow is outside this interior model')
    result=list(values)
    for j in range(len(values)-window+1):
        result[j]=sum(values[j:j+window])//window
    return result
