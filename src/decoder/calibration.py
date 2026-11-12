"""Inferred calibration fields, with fail-closed consistency checks."""
MEASURES = ('max_v','min_v','mean_v','rms_v','peak_v','peak_to_peak_v')
TIMED_MEASURES = (('frequency_hz',1e3),('period_s',1e12),('positive_width_s',1e12),('negative_width_s',1e12),('positive_duty_percent',100),('negative_duty_percent',100))


def fields(data, metadata, channels):
    end=metadata['sections'][0]['offset']+metadata['sections'][0]['length']
    if end < 0x1C8 or end-240 < 0x1C8:
        return {'status':'unavailable: settings layout too short'}
    u=lambda o,n=8: int.from_bytes(data[o:o+n],'big',signed=False)
    signed=lambda o,n=8: int.from_bytes(data[o:o+n],'big',signed=True)
    horizontal=u(0x4A,2)
    vertical=u(0x4E,2)
    coordinate_scale=u(0xE4,4)
    if not (0<horizontal<=4096 and 0<vertical<=4096 and 0<coordinate_scale<=65536):
        return {'status':'unavailable: invalid or unsupported saved coordinate geometry'}
    per_pixel=u(0x1C0,4)
    acq_time=u(0x1AF)/1e12
    result={'status':'reference-checked timing and 1X voltage model; not a hardware accuracy calibration',
            'display_seconds_per_div':u(0x190)/1e12,
            'capture_seconds_per_div':acq_time,
            'samples_per_pixel_candidate':per_pixel,
            'coordinate_geometry':{'horizontal_pixels_per_div':horizontal,'vertical_pixels_per_div':vertical,'raw_units_per_pixel':coordinate_scale,'basis':'serialized state fields and firmware initialization/measurement code'},
            'sample_interval_s_candidate':acq_time/(horizontal*per_pixel) if acq_time>0 and per_pixel in (25,50) else None,
            'time_origin':'first exported sample; trigger time unknown',
            'timing_basis':'saved horizontal grid geometry; reference-checked at 95 pixels/div on CH1, CH2 and both channels',
            'channels':{}}
    base=end-240
    for name,raw in channels.items():
        if name not in ('CH1','CH2'):continue
        i=int(name[-1])-1; shift=i*0x41
        display_gain=u(0x6D+shift)/1e6
        gain=u(0x75+shift)/1e6
        position=signed(0x81+shift,4)
        measurements={key:signed(base+i*96+j*8)/1e6 for j,key in enumerate(MEASURES)}
        measurements.update({key:signed(base+i*96+(6+j)*8)/scale for j,(key,scale) in enumerate(TIMED_MEASURES)})
        slope=gain/(coordinate_scale*vertical);zero=(position+.5)*coordinate_scale
        predicted_max=(max(raw)-zero)*slope
        predicted_min=(min(raw)-zero)*slope
        quantum=gain/vertical
        residuals=([(predicted_max-measurements['max_v'])/quantum,
                    (predicted_min-measurements['min_v'])/quantum] if quantum>0 else None)
        tolerance=max(0.,measurements['peak_to_peak_v'])*0.02+2*quantum
        strict=bool(residuals and max(abs(x) for x in residuals)<=1.5)
        valid=bool(0<gain<=1000 and abs(position)<=10000 and residuals and
                   max(abs(predicted_max-measurements['max_v']),abs(predicted_min-measurements['min_v']))<=tolerance and
                   measurements['max_v']>=measurements['min_v'])
        result['channels'][name]={
            'display_volts_per_div':display_gain,'capture_volts_per_div':gain,
            'capture_zero_position':position,'display_zero_position':signed(0x7D+shift,4),'candidate_volts_per_count':slope,
            'candidate_zero_raw':zero,'stored_readouts':measurements,
            'stored_readouts_basis':'instrument-produced; firmware supports multi-update accumulation; averaging depth for this capture is unknown',
            'endpoint_residual_adc_steps':residuals,'conversion_usable':valid,
            'strict_extrema_agreement':strict,'plausibility_tolerance_v':tolerance,
            'consistency': ('strict extrema agreement' if strict else 'plausible conversion; extrema differ between samples and stored readouts') if valid else 'conflict; voltage conversion disabled',
            'confidence':'coordinate model checked on supplied 0 V, DC and 1X square-wave references; other probe factors remain unverified'}
    return result


def volts(metadata, channels):
    calibration=metadata.get('calibration',{})
    info=calibration.get('channels',{})
    if not channels or any(not info.get(name,{}).get('conversion_usable') for name in channels):
        raise ValueError('Voltage conversion unavailable: sample extrema conflict with stored readouts, or calibration fields are unknown. Use raw mode.')
    return {name:[(value-info[name]['candidate_zero_raw'])*info[name]['candidate_volts_per_count'] for value in raw]
            for name,raw in channels.items()}
