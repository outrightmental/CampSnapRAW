# Roadmap

## Phase 0 — Recon (current)

- [ ] Teardown: identify the main SoC (photo of chip markings)
- [ ] Identify the image sensor (FPC markings or firmware strings)
- [ ] Identify the SPI NOR flash chip (package, capacity)
- [ ] Locate UART/debug pads on the board, if any
- [ ] Catalogue official CS-Pro firmware update files (hashes + URLs only)
- [ ] Document exact dial positions and electrical readout (GPIO vs ADC ladder)
- [ ] Collect community `.flt` files and map the format with `flt_inspect.py`

## Phase 1 — Firmware acquisition

- [ ] Obtain a full firmware image via the official update path (if Camp Snap
      publishes CS-Pro updates, the update file itself is a partial/full image)
- [ ] Fallback: in-circuit SPI flash dump (SOIC-8 clip + CH341A or similar)
- [ ] Verify dump integrity (two reads, matching hashes)
- [ ] Run `fw_identify.py`; identify architecture, load address, compression
- [ ] Establish a known-good restore procedure **before any modification**

## Phase 2 — Static reverse engineering

- [ ] Load in Ghidra with correct arch/base address
- [ ] Locate: SD/FAT write routines, JPEG encoder entry, capture interrupt path
- [ ] Locate: dial position read + mode table
- [ ] Locate: sensor configuration (resolution, bit depth, CFA order, black level)
- [ ] Find the raw Bayer frame buffer address and its lifetime during capture

## Phase 3 — First RAW

- [ ] Minimal patch: after capture, write the Bayer buffer to `NNNN.RAW` on
      the card alongside (or instead of) the JPEG
- [ ] Write a metadata sidecar (exposure time, gain) if registers are readable
- [ ] Develop on PC with `tools/dng_wrap.py`; verify CFA order and levels
- [ ] Timing/stability testing: burst shots, full card, low battery

## Phase 4 — The real firmware

- [ ] Dial neutralization: all non-OFF positions → identical RAW capture
      (see docs/dial-behavior.md)
- [ ] Remove/skip JPEG encode for speed and battery (config option)
- [ ] Package as xdelta patch + flashing guide + recovery guide
- [ ] Community beta

## Phase 5 — Stretch goals

- [ ] In-camera DNG (skip the PC wrap step)
- [ ] RAW+JPEG mode
- [ ] Proper ColorMatrix1 calibration for the sensor (color chart shots)
- [ ] Long-exposure / gain hacks, if the sensor driver allows
