"""Observed layout checks. Structural agreement never identifies firmware version."""
PROFILE='dpos350p-observed-layout-1'
FIRMWARE_SHA256='6635ddd661fa6aa6a36672c1428e74d0f78913a24fd5a425cebedff0acefd58c'

def assess(data,metadata):
    end=metadata['sections'][0]['offset']+metadata['sections'][0]['length']
    reasons=[];shape=False;geometry=False
    if end>=0x26A:
        frames=int.from_bytes(data[0x1A4:0x1A6],'big')
        expected=0x26A+12*frames+261
        shape=0<=frames<=50 and end==expected
        if not shape:reasons.append('Settings length does not match the inspected fixed-prefix/frame-table/trailer contract')
        observed=tuple(int.from_bytes(data[o:o+2],'big') for o in (0x36,0x38,0x4A,0x4E))
        scale=int.from_bytes(data[0xE4:0xE8],'big')
        geometry=observed==(950,503,95,63) and scale==64
        if not geometry:reasons.append('Coordinate geometry differs from the reference-checked profile')
    else:reasons.append('Settings block is too short for the inspected layout')
    return {'profile':PROFILE if shape else None,
            'settings_layout_matched':shape,'conversion_geometry_matched':geometry,
            'numeric_model_allowed':shape and geometry,
            'producer_firmware_version':None,
            'firmware_origin_status':'not established from capture bytes',
            'inspected_firmware_sha256':FIRMWARE_SHA256,
            'cross_version_validation':False,
            'status':'observed layout match; firmware version unverified' if shape and geometry else 'unrecognized layout or geometry; physical conversion disabled',
            'reasons':reasons}
