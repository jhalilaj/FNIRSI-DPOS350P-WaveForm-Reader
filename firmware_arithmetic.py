"""Recovered measurement-coordinate arithmetic, not a full acquisition emulator."""
def signed_divide(numerator,denominator):
    if denominator==0:raise ValueError('Zero divisor')
    value=abs(numerator)//abs(denominator)
    return -value if (numerator<0)!=(denominator<0) else value


def coordinate_readout_microvolts(word,zero_position,range_microvolts,raw_units_per_pixel=64,vertical_pixels_per_div=63):
    """Quantize an unsigned measurement-buffer coordinate, then signed integer divide.

    This models the observed readout path; do not replace a continuous trace with it.
    """
    if not 0<=word<=65535:raise ValueError('Expected an unsigned 16-bit coordinate')
    if raw_units_per_pixel<=0 or vertical_pixels_per_div<=0:raise ValueError('Invalid coordinate geometry')
    coordinate=word//raw_units_per_pixel
    return signed_divide((coordinate-zero_position)*range_microvolts,vertical_pixels_per_div)
