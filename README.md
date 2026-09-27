# campsnap-pro-raw

**Community firmware project to make the Camp Snap Pro (CS-Pro) shoot camera RAW.**

The CS-Pro is a screen-free 16 MP point-and-shoot that only writes filtered JPEGs.
This project aims to change that: every press of the shutter captures the raw Bayer
sensor data to the SD card, which you can develop on your computer as a DNG.

> **Status: Phase 0 — Research.** No working RAW firmware exists yet, here or
> anywhere. The CS-Pro's firmware has not been publicly reverse engineered. This
> repo is the scaffold, tooling, and knowledge base to get there. See
> [ROADMAP.md](ROADMAP.md) for the plan and [CONTRIBUTING.md](CONTRIBUTING.md)
> for how to help.

## Design goals

1. **RAW, always.** Every shot is captured as raw sensor data (later: in-camera
   DNG). No JPEG pipeline, no baked-in look.
2. **The top dial becomes power only.** On stock firmware the dial selects
   between OFF and the four filter looks (STD / VTG1 / VTG2 / B&W). With this
   firmware, *any* non-OFF position behaves identically: camera on, shooting
   RAW. The filter positions are deliberately ignored. OFF still means off.
   Spec: [docs/dial-behavior.md](docs/dial-behavior.md).
3. **Recoverable.** No mod ships unless there is a documented path back to
   stock firmware.
4. **Legal to share.** We never redistribute Camp Snap's copyrighted firmware.
   Mods are distributed as binary *patches* (xdelta/bsdiff) you apply to your
   own copy of the stock firmware.

## Why this is plausible

- Camp Snap has a history of being mod-friendly: the company openly supports
  custom filter (`.flt`) files, and community firmware hacks exist for the
  original camera (see [prokrypt/campsnap-fun](https://github.com/prokrypt/campsnap-fun)).
- All Camp Snap models to date update firmware from files dropped onto the
  SD/TF card — meaning the flash path is user-accessible, no soldering needed
  to *install* mods once they exist.
- Cameras in this class run a single-chip SoC (sensor → ISP → JPEG encoder →
  SD). The raw Bayer frame necessarily exists in a DRAM buffer before JPEG
  encoding. RAW capture means finding that buffer and writing it to the card —
  the same trick CHDK pulled off on Canon compacts years ago.

**The catch:** the CS-Pro uses a *different SoC* than the original Camp Snap
(confirmed by the founder in press interviews), so none of the existing V1xx
hacks carry over. Phase 0 is identifying that chip and getting a firmware dump.

## Repo layout

```
docs/
  hardware.md        What we know about the CS-Pro hardware + teardown checklist
  firmware.md        Update mechanisms, file formats (.brn/.flt), dump strategies
  raw-pipeline.md    Where RAW lives in the pipeline and how we intercept it
  dial-behavior.md   Spec for "dial = power only, everything is RAW"
tools/
  fw_identify.py     Triage an unknown firmware dump (entropy, strings, SoC hints)
  flt_inspect.py     Analyze/diff .flt filter files to learn the color pipeline
  dng_wrap.py        Wrap a raw Bayer dump into a valid DNG (works today)
firmware/            Local-only workspace for YOUR dumps. Never committed.
patches/             Future home of xdelta patches against stock firmware.
```

## Tools quickstart

Python 3.10+, no required dependencies (numpy optional, for speed).

```bash
# Triage a firmware dump
python3 tools/fw_identify.py firmware/cspro-dump.bin

# Compare two filter files to map what bytes control the look
python3 tools/flt_inspect.py std.flt vtg1.flt

# Turn a raw Bayer dump into a DNG you can open in darktable/RawTherapee
python3 tools/dng_wrap.py frame.raw -o frame.dng -W 4608 -H 3456 \
    --bpp 10 --pack mipi --cfa RGGB
```

`dng_wrap.py` is fully functional now — the moment anyone extracts a single raw
frame from the camera (even via a debug mode or memory dump), we can develop it.

## How to help right now

- **Own a CS-Pro?** Open it up and photograph the board. The marking on the
  main SoC is the single most valuable piece of information this project needs.
  Checklist in [docs/hardware.md](docs/hardware.md).
- **Have official CS-Pro firmware update files?** Don't upload them — record
  filename, SHA-256, and source URL in an issue. See
  [docs/firmware.md](docs/firmware.md).
- **Good with Ghidra?** Watch this repo; disassembly work starts the moment we
  have a dump.

## Safety & disclaimers

- Flashing modified firmware **can permanently brick your camera** and voids
  your warranty. Everything here is at your own risk.
- This project is **not affiliated with or endorsed by Camp Snap**. They're a
  small team making a nice product — buy their cameras, be kind in their
  support inbox.

## Prior art & inspiration

- [prokrypt/campsnap-fun](https://github.com/prokrypt/campsnap-fun) — firmware
  hacks and hardware notes for the original Camp Snap
- [CHDK](https://chdk.fandom.com/wiki/CHDK) and
  [Magic Lantern](https://magiclantern.fm/) — proof that adding RAW to
  JPEG-only cameras is a solved class of problem

## License

MIT for everything in this repo. Camp Snap's firmware remains theirs and is
never distributed here. See [LICENSE](LICENSE).
