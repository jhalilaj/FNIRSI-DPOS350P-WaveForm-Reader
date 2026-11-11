"""Confirmed saved trigger controls and scope measurement selection IDs."""
METRICS={
 'max':('MAX','maximum','amplitude'),'min':('MIN','minimum','amplitude'),
 'avg':('AVG','mean','amplitude'),'rms':('RMS','rms','amplitude'),
 'peak':('PEAK',None,'amplitude'),'vpp':('Vpp','peak_to_peak','amplitude'),
 'freq':('F','frequency_hz','Hz'),'period':('T','period_s','s'),
 'high':('HIGH','positive_width_s','s'),'low':('LOW','negative_width_s','s'),
 'duty+':('DUTY+','duty_percent','%'),'duty-':('DUTY-',None,'%'),
 'ac_rms':('AC RMS','ac_rms','amplitude'),'rise':('RISE','rise_time_s','s'),'fall':('FALL','fall_time_s','s')}
SCOPE_IDS=dict(enumerate(list(METRICS)[:12],1))

def saved_selection(data,metadata):
    if not metadata.get('compatibility',{}).get('numeric_model_allowed'):return {'status':'unavailable','entries':[]}
    end=metadata['sections'][0]['offset']+metadata['sections'][0]['length']
    ids=[int.from_bytes(data[p:p+2],'big',signed=True) for p in range(end-48,end,2)]
    entries=[];unknown=[]
    for value in ids:
        if not value:continue
        if abs(value) not in SCOPE_IDS:unknown.append(value);continue
        item=('CH1' if value>0 else 'CH2',SCOPE_IDS[abs(value)])
        if item not in entries:entries.append(item)
    return {'status':'mapped signed measurement IDs','entries':entries,'raw_ids':ids,'unknown_ids':unknown}

def trigger_info(metadata):
    t=metadata.get('calibration',{}).get('trigger',{})
    if not t:return {'text':'Trigger: unavailable for this file','channel':None,'level_v':None}
    channel={0:'CH1',1:'CH2'}.get(t.get('trigger_channel_raw'))
    edge={0:'Rising',1:'Falling'}.get(t.get('trigger_edge_raw'),'Unknown edge')
    enabled={0:'Disabled',1:'Enabled'}.get(t.get('trigger_enabled_raw'),'Unknown state')
    info=metadata['calibration'].get('channels',{}).get(channel,{})
    geometry=metadata['calibration'].get('coordinate_geometry',{})
    vertical=geometry.get('vertical_pixels_per_div')
    level=None
    if vertical and info.get('conversion_usable'):
        level=(t['trigger_level_coordinate_raw']-info['display_zero_position'])*info['display_volts_per_div']/vertical
    text=f'Trigger: {channel or "Unknown channel"} | {edge} | {enabled}'
    text+=f' | saved level ≈ {level:+.5g} V' if level is not None else ' | physical level unavailable'
    return {'text':text,'channel':channel,'level_v':level,'enabled':enabled=='Enabled','edge':edge}

def measurement_text(metric,m,amplitude_unit):
    label,key,unit=METRICS[metric]
    if metric=='peak':value=m['maximum'] if abs(m['maximum'])>=abs(m['minimum']) else m['minimum']
    elif metric=='duty-':value=100-m['duty_percent'] if m.get('duty_percent') is not None else None
    else:value=m.get(key)
    return f'{label} '+('—' if value is None else f'{value:.6g} {amplitude_unit if unit=="amplitude" else unit}')
