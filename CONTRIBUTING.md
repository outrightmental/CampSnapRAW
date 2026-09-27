# Contributing

Everyone is welcome. The project needs very different skill sets — you don't
need to know reverse engineering to be useful.

## What we need most (in order)

1. **A photo of the CS-Pro main board**, especially the SoC markings. If you're
   comfortable opening yours, follow the checklist in `docs/hardware.md` and
   open an issue with photos.
2. **Firmware file intel.** If Camp Snap publishes a CS-Pro firmware update:
   record the filename, SHA-256, size, and download URL in an issue.
3. **`.flt` filter file analysis.** Run `tools/flt_inspect.py` on community
   filter files and post findings. Understanding the filter format teaches us
   about the color pipeline and the SoC vendor's SDK.
4. **Ghidra reversers** — once a dump exists.
5. **Testers with a camera they can afford to brick** — Phase 3 onward.

## Ground rules

- **Never commit Camp Snap's firmware, in whole or part.** Not the stock
  images, not official update files, not decompressed sections. Their code is
  their copyright. Share *hashes*, *offsets*, *annotations*, and *your own*
  analysis/patches instead. Mods ship as binary diffs (xdelta3/bsdiff) that
  users apply to firmware they obtained themselves.
- Same rule for third-party `.flt` files that aren't freely licensed — link,
  don't mirror.
- Interoperability-focused reverse engineering of a device you own is broadly
  accepted, but laws vary by country. You are responsible for your own
  compliance.
- Mark untested patches loudly. Somebody's camera is on the line.
- Be kind. Especially about Camp Snap themselves — they've been friendly to
  modders, and we'd like to keep it that way.

## Dev setup

- Python 3.10+ (tools are stdlib-only; `numpy` optional for speed)
- Useful extras: `exiftool`, `binwalk`, `xdelta3`, [Ghidra](https://ghidra-sre.org/)
- Run tool self-checks: `python3 tools/dng_wrap.py --selftest`

## Issue labels

- `hw-intel` — teardown photos, chip IDs, pinouts
- `fw-intel` — firmware file sightings, hashes, update mechanism notes
- `flt` — filter format findings
- `re` — disassembly findings
- `patch` — proposed firmware modifications
