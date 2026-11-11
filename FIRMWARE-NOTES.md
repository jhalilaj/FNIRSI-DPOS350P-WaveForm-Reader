# Firmware and documentation investigation

## Inputs reviewed

Read-only sources from the supplied `DPOS350P_Firmware_file` folder:
- DPOS350P-FNIRSI-2025619.iso
- DPOS350P_Manual_EN_ES_PT_V1.6.pdf
- DPOS350P Update Step & Log.txt

No device connection, firmware installation, or firmware execution was performed. The provided firmware is not evidence of which version produced the existing WAV captures.

## Package findings

The 948,310-byte firmware has SHA-256:

    6635ddd661fa6aa6a36672c1428e74d0f78913a24fd5a425cebedff0acefd58c

It starts with DPOS350P and contains eGON.BMP at file offset 0x1004 and eGON.EXE at 0x51004. These identify embedded image/executable records, rather than a conventional ISO filesystem. The executable record starts at 0x51000, with its payload at 0x51020.

An analysis-only ELF wrapper was constructed around the executable payload to inspect its ARM instructions with LLVM. The wrapper was never executed. The vector table contains ARM LDR PC instructions and handler addresses around 0x4008CB28. Mapping payload byte zero to 0x40000000 places actual ARM startup instructions at that handler address; omitting the 32-byte package header is essential for correct mapping.

A literal reference at virtual address 0x400365F0 points to 0x4008E2D0, the string /Waveform/number_table.sys. Another at 0x40048F9C points to 0x4008ED48, the waveform-saving status text. The second reference belongs to UI text setup, not evidence of the waveform serializer. These references establish useful investigation landmarks but do not prove the calibration equations.

The executable is unstripped raw code/data without an ELF symbol table in the package. No source code or explicit WAV layout specification was supplied. Full control-flow tracing of save/load and measurement routines remains unfinished.

## Manual findings

English printed pages 18-19 (PDF pages 22-23) state that:
- Saved WAVs contain data for currently enabled channels.
- Waveform-browser recall pauses acquisition and allows zoom, measurements and cursors on the loaded capture.
- Physical resolution is 8 bits; higher displayed resolution uses digital filtering.
- Probe attenuation settings include 1X, 10X and 100X.

The save/recall behavior supports interpreting saved channel/configuration state rather than treating the file as ordinary audio. The resolution statement does not by itself establish the meaning of our 16-bit fixed-point sample words. The manual provides no export-byte specification, no proof of the 100-pixels/div timing assumption, and no published equation for the retained sample-to-voltage conversion.

The June 19, 2025 changelog includes a correction for channel-to-channel phase difference and a correction involving measurement names Du/DT. These are reasons to track firmware provenance during validation; they do not establish a cause for the inconsistencies in files 4, 10 and 11.

## Decoder impact

No inferred calibration has been promoted to manufacturer-confirmed status. The existing extrema consistency gate and raw-only fallback for files 4, 10 and 11 remain in place. Timing and trigger-relative coordinates remain unverified.

Added firmware_inspect.py provides a repeatable read-only package inventory and SHA-256 check. It does not modify the image, execute it, or install it. firmware-manifest.json records the supplied package.

Next investigation targets: trace the waveform save/load serializer, identify channel record loops and byte writers, trace horizontal coordinate conversion, and compare firmware-derived conversions against the existing 17-file corpus. External reference captures remain necessary to validate physical accuracy, even if the software formulas are recovered.
