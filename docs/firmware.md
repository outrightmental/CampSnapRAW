# Firmware notes

## How Camp Snap firmware updates work (family history)

All models to date flash from files placed in the **root of the memory card**,
then power-cycling. This is our installation path once patches exist.

| Model | Mechanism (public record) |
|---|---|
| V101 (original, LED counter) | Copy `ISP.bin` first, then `1628.bin` (+ third file); camera shows `---` ~20 s, run twice. `ISP.bin`-first protects against bricking |
| V103 | Single `.brn` file to card root; LED blinks green/red while flashing |
| V105 | Ships with custom-filter support built in; `.flt` files instead of firmware swaps for look changes |
| CS-Pro | `.flt` support via `std.flt` / `vtg1.flt` / `vtg2.flt` / `bw.flt` in card root. **Full-firmware update mechanism not yet documented here** — if Camp Snap publishes a Pro updater, that file is our Rosetta stone |

Takeaways:

- The bootloader reads and flashes from FAT — meaning a *software-only* install
  path exists, and (from V101's two-stage design) some recovery logic exists too.
- **Task (`fw-intel`):** find and hash any official CS-Pro update file. Record
  filename, size, SHA-256, source URL in an issue. Do not upload the file.

## Getting a full dump if no update file surfaces

1. **USB modes:** probe for hidden modes (holding buttons while connecting,
   vendor SCSI commands). Some camera SoCs expose a ROM/recovery USB mode with
   full flash read. Record USB VID:PID in every mode you find.
2. **In-circuit SPI read:** if the board uses SOIC-8 SPI NOR, a test clip +
   CH341A programmer (`flashrom`) can dump without desoldering. Dump twice,
   compare hashes. Battery disconnected, flash cap discharged.
3. **UART:** if debug pads exist, the boot log alone usually names the SoC,
   SDK version, and memory map. Jackpot if there's a shell.

Whatever the source: `python3 tools/fw_identify.py dump.bin` for first triage.

## `.flt` filter files

The community makes custom color profiles; the Pro loads them per dial
position. The format is not documented in this repo yet.

Why we care even though our goal is to *bypass* filters entirely:

- The `.flt` loader code is an easy landmark to find in the disassembly, and it
  touches the ISP configuration — the exact subsystem RAW capture must tap.
- If `.flt` turns out to contain ISP register blocks or LUT tables, it reveals
  buffer layouts and register names for free.

**Task (`flt`):** collect freely-shared `.flt` files, run
`tools/flt_inspect.py a.flt b.flt`, and post structure findings (sizes,
headers, which byte ranges differ between looks).

## Rules

Per [CONTRIBUTING.md](../CONTRIBUTING.md): no vendor binaries in this repo,
ever. `firmware/` is a gitignored local workspace. We publish *hashes,
offsets, annotations, and patches* — never the images themselves.
