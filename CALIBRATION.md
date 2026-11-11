# Reference update — current behavior

The seven new reference pairs were processed. See reference-validation/REPORT.md and results.json for measurements and acceptance bounds. The timing divisor is now **95 pixels/div**, replacing the earlier 100-pixel hypothesis below. The known 1 kHz source decodes as 1000.25–1000.34 Hz across tested layouts and timebases. This verifies the tested conditions against the declared source, not a traceable clock calibration.

Zero-input mean is -2.10 mV. The nominal 5 V DC capture decodes as 4.86796 V, matching the scope readout around 4.87 V. Square-wave plateau spans are 4.881–4.927 Vpp versus the declared 5 Vpp, a 1.5–2.4% difference; no correction was fitted to force 5 V. The offset is 0.493–0.503 V. CH2-only data and independent channel-zero compensation are now checked.

The strict 1.5-ADC-step extrema check is retained as a diagnostic. Conversion additionally permits a declared plausibility envelope of 2% of stored Vpp plus two ADC steps, to accommodate frame differences and edge excursions. This is not an accuracy claim. The three old inconsistent files still fail. Earlier descriptions below of strict rejection and untested CH2-only layout are historical and superseded by this update.

## Earlier investigation record

# Calibration findings — second milestone

## What now works

The viewer can switch between raw counts and inferred volts. Scope-stored voltage readouts are available in Measurements. The CLI supports --calibrated and exports inferred-calibration.csv with explicitly named inferred voltage and relative-time columns.

All 17 files still open in raw mode. Fourteen files pass the voltage-extrema consistency check. Files 4, 10 and 11 fail it; their voltage conversion is disabled. Their raw samples, scope preview and stored readouts remain accessible.

## Recovered fields

Offsets below are absolute bytes from the start of the file, in the observed firmware layout. All multibyte values are big-endian.

| Field | CH1 offset | CH2 offset | Encoding |
|---|---|---|---|
| Current display range | 0x6D | 0xAE | uint64, microvolts/div |
| Range retained for captured samples | 0x75 | 0xB6 | uint64, microvolts/div |
| Zero-position retained for captured samples | 0x81 | 0xC2 | int32, coordinate units |

Current timebase: uint64 at 0x190, interpreted as picoseconds/div. Retained capture timebase: uint64 at 0x1AF, same interpretation. Candidate samples per horizontal pixel: uint32 at 0x1C0, 25 for the dual-channel files and 50 for the single-channel files.

The voltage readout trailer begins 240 bytes before the preview section. There are twelve signed int64 fields per channel, 96 bytes apart. The first six are interpreted as max, min, mean, RMS, signed peak and peak-to-peak, in microvolts. The other six are not exposed as physical measurements yet. Following the trailer location rather than a fixed address handles the three different settings-section lengths.

Stored readouts agree with visible screenshot text in several cases: 5.wav contains approximately 47.46 / -8.41 / 5.57 V for CH1 max/min/mean and 5.79 / 5.24 / 5.50 V for CH2, matching the readouts seen in 1.bmp. 14.wav contains approximately 6.154 / 5.678 / 5.900 V, consistent with the readouts in 8.bmp. These observations compare readouts; they do not establish that the screenshots and waveforms are precisely the same acquisition.

## Voltage hypothesis

    volts = (raw_u16 - 64 * capture_zero_position - 32)
            * capture_volts_per_div / 4032

Here 4032 = 64 * 63. This suggests fixed-point coordinate values with a half-code offset and 63 coordinate units/div. It is an inferred representation, not a manufacturer-confirmed ADC transfer function.

The candidate converted min/max must agree with the scope-stored min/max within 1.5 ADC steps, where one step is capture_volts_per_div / 63. This is a consistency gate, not an accuracy specification. Passing it cannot establish gain accuracy, zero accuracy, probe compensation or correct timing. Mean/RMS values sometimes disagree substantially and must not be treated as independently validated.

Files 14 and 15 provide a useful held-acquisition regression: display range changes from 2 V/div to 1 V/div, while retained capture range stays 2 V/div and the sample words remain identical. The resulting inferred voltages are therefore identical. Using the current display range would have incorrectly halved the voltage.

## Timing hypothesis

    candidate_interval_s = capture_seconds_per_div
                           / (100 * samples_per_pixel_candidate)

The count patterns correspond to 950 * 25 + 2 words/channel for dual-channel captures, or 950 * 50 + 4 for single-channel captures. This suggests a 950-pixel buffer with additional edge samples. The formula assumes 100 horizontal pixels/div; neither that assumption nor the purpose of the edge samples is externally verified. Time zero is the first exported word, not the trigger. Do not use the inferred timing for precision frequency or delay measurements yet.

File 9 also separates display and retained timebases: 10 ms/div versus 20 ms/div. Inferred timing uses the retained value.

## Validation performed

- All 17 files load in the updated viewer.
- All 14 eligible files switch to inferred voltage and back to raw.
- Thirteen automated tests pass, including variable readout trailers, retained-vs-display scale, unknown-calibration rejection and conflicting-readout rejection.
- Files 14/15 produce identical inferred voltage arrays.
- File 9 preserves distinct display/capture timebases.
- The CLI refuses inferred export for file 4 with a clear error.

## What is still needed

A capture of a signal whose amplitude and frequency are independently known, with a matching screenshot of the same stopped acquisition, is required to validate the conversion rather than only its internal consistency. Trigger-relative timing, probe-factor encoding, CH2-only behavior and the inconsistent files remain unresolved.
