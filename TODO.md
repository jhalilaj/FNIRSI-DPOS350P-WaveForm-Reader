# Current scope and future work

Current scope: FNIRSI DPOS350P files used with 1X probes. The viewer supports raw and model-converted voltage, relative and trigger-marker time, channel toggles, cursor readings, zoom/pan, CSV and SVG export.

Deferred at the user's request:
- 10X and 100X probe interpretation and validation.
- Investigating original corpus files 4.wav, 10.wav and 11.wav. Their discrepancies have not been established to be caused by probe settings. Keep raw viewing available and model voltage conversion blocked.

Other future precision work:
- Resolve the difference between the displayed trigger marker and the actual threshold-crossing instant, including filtering/edge-sample offsets.
- Verify channel phase/delay and other firmware/timebase variants.
- Investigate the 1.5–2.4% nominal square-wave amplitude difference using an independently measured source.
