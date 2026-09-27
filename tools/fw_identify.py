#!/usr/bin/env python3
"""fw_identify.py — first-pass triage of an unknown camera firmware image.

Reports hashes, an entropy map (find compressed/encrypted vs code/padding
regions), embedded file signatures, ARM vector-table heuristics, and hunts
for strings that identify the SoC vendor, SDK, and image sensor.

Usage:
    python3 fw_identify.py DUMP.bin [-v] [--min-str 6]

Stdlib only. MIT.
"""

import argparse
import hashlib
import math
import re
import struct
import sys
from pathlib import Path

MAGICS = [
    (b"\x7fELF", "ELF binary"),
    (b"\xff\xd8\xff", "JPEG (UI asset or thumbnail?)"),
    (b"\x89PNG\r\n", "PNG image"),
    (b"PK\x03\x04", "ZIP container"),
    (b"\x1f\x8b\x08", "gzip stream"),
    (b"7zXZ\x00", "xz stream"),
    (b"BZh9", "bzip2 stream"),
    (b"hsqs", "SquashFS (LE)"),
    (b"sqsh", "SquashFS (BE)"),
    (b"UBI#", "UBI volume"),
    (b"UBI!", "UBIFS"),
    (b"CR32", "generic CRC32 table marker"),
    (b"Exif\x00\x00", "EXIF block (SDK defaults may name the vendor!)"),
    (b"RIFF", "RIFF (WAV beep assets?)"),
    (b"FAT1", "FAT boot sector fragment"),
    (b"MSDOS5.0", "FAT formatter string"),
]

# Case-insensitive vendor / SDK / toolchain hints.
VENDOR_HINTS = [
    ("icatch", "iCatchtek — original Camp Snap family used iCatch (USB 04fc)"),
    ("sunplus", "Sunplus (iCatch lineage)"),
    ("spca", "Sunplus/iCatch SPCA SoC family"),
    ("sonix", "Sonix"),
    ("sn9c", "Sonix SN9C SoC family"),
    ("jieli", "JieLi (JL)"),
    ("anyka", "Anyka AKxx"),
    ("ak37", "Anyka AK37xx"),
    ("ak39", "Anyka AK39xx"),
    ("buildwin", "Buildwin"),
    ("goke", "Goke GKxxxx"),
    ("generalplus", "Generalplus"),
    ("novatek", "Novatek"),
    ("nt966", "Novatek NT966xx"),
    ("ingenic", "Ingenic (MIPS/XBurst)"),
    ("hisilicon", "HiSilicon"),
    ("hi35", "HiSilicon Hi35xx"),
    ("allwinner", "Allwinner"),
    ("rockchip", "Rockchip"),
    ("mstar", "MStar"),
    ("realtek", "Realtek"),
    ("xuantie", "T-Head XuanTie (RISC-V core)"),
    ("risc-v", "RISC-V toolchain reference"),
    ("cortex", "ARM Cortex core reference"),
    ("armcc", "ARM Compiler toolchain"),
    ("gcc", "GCC toolchain string"),
    ("drampara", "DRAMPARA — DRAM parameter file (seen on original Camp Snap)"),
    ("isp.bin", "two-stage updater reference (V101-style)"),
    (".brn", "BRN firmware update reference (V103-style)"),
    (".flt", "filter-file loader reference"),
    ("bayer", "raw Bayer handling code"),
    ("raw10", "RAW10 pixel format reference"),
    ("raw12", "RAW12 pixel format reference"),
    ("dng", "DNG reference (!)"),
    ("campsnap", "Camp Snap branding string"),
    ("camp snap", "Camp Snap branding string"),
]

# Image sensor part-number patterns.
SENSOR_PATTERNS = [
    (r"\bOV[0-9]{4,5}[A-Z]{0,2}\b", "OmniVision"),
    (r"\bIMX[0-9]{3}[A-Z]{0,3}\b", "Sony"),
    (r"\bGC[0-9]{4}[A-Z]{0,2}\b", "GalaxyCore"),
    (r"\bSC[0-9]{3,4}[A-Z]{0,3}\b", "SmartSens"),
    (r"\bS5K[0-9A-Z]{3,6}\b", "Samsung"),
    (r"\bHI-?[0-9]{3,4}\b", "Hynix (SK hynix sensor)"),
    (r"\bMN[0-9]{5}\b", "Panasonic"),
    (r"\bAR[0-9]{4}\b", "onsemi/Aptina"),
]

WINDOW = 4096


def shannon(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    ent = 0.0
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent


def entropy_map(data: bytes):
    """Yield (offset, entropy) per window."""
    for off in range(0, len(data), WINDOW):
        yield off, shannon(data[off : off + WINDOW])


def merge_spans(offsets, window=WINDOW):
    """Merge consecutive window offsets into (start, end) spans."""
    spans = []
    for off in offsets:
        if spans and off <= spans[-1][1]:
            spans[-1][1] = off + window
        else:
            spans.append([off, off + window])
    return [(a, b) for a, b in spans]


def extract_strings(data: bytes, min_len: int):
    """Yield (offset, string) for printable ASCII runs."""
    pat = re.compile(rb"[\x20-\x7e]{%d,}" % min_len)
    for m in pat.finditer(data):
        yield m.start(), m.group().decode("ascii", "replace")


def arm_vector_heuristics(data: bytes):
    """Look for classic ARM32 exception vectors at offset 0."""
    notes = []
    if len(data) < 64:
        return notes
    words = struct.unpack("<8I", data[:32])
    if all((w >> 24) == 0xEA for w in words):
        notes.append("offset 0: eight ARM 'B' instructions — classic ARM7/ARM9 vector table")
    elif all((w & 0xFFFFF000) == 0xE59FF000 for w in words):
        notes.append("offset 0: eight 'LDR PC, [PC, #imm]' — ARM literal-pool vector table")
    else:
        sp, rst = words[0], words[1]
        if 0x10000000 <= sp <= 0x20FFFFFF and (rst & 1) and rst < 0x2100_0000:
            notes.append(
                f"offset 0: SP=0x{sp:08x}, reset=0x{rst:08x} (thumb) — "
                "possible Cortex-M style vector table"
            )
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image", type=Path)
    ap.add_argument("--min-str", type=int, default=6, help="min string length (default 6)")
    ap.add_argument("-v", "--verbose", action="store_true", help="dump more strings")
    args = ap.parse_args()

    data = args.image.read_bytes()
    n = len(data)

    print(f"== {args.image.name} ==")
    print(f"size    : {n} bytes ({n/1024/1024:.2f} MiB)")
    print(f"md5     : {hashlib.md5(data).hexdigest()}")
    print(f"sha256  : {hashlib.sha256(data).hexdigest()}")
    print(f"entropy : {shannon(data):.3f} bits/byte overall")

    # Entropy regions
    high, low = [], []
    for off, e in entropy_map(data):
        if e > 7.9:
            high.append(off)
        elif e < 0.5:
            low.append(off)
    print("\n-- entropy map --")
    hs = merge_spans(high)
    ls = merge_spans(low)
    if hs:
        print("high-entropy (compressed/encrypted?) spans:")
        for a, b in hs[:20]:
            print(f"  0x{a:08x} - 0x{b:08x} ({(b - a)//1024} KiB)")
        if len(hs) > 20:
            print(f"  ... and {len(hs) - 20} more")
    else:
        print("no high-entropy spans — image likely uncompressed and unencrypted (good news)")
    if ls:
        print("near-empty (padding) spans:")
        for a, b in ls[:10]:
            print(f"  0x{a:08x} - 0x{b:08x}")

    # Magic signatures
    print("\n-- embedded signatures --")
    any_magic = False
    for magic, desc in MAGICS:
        hits = []
        start = 0
        while True:
            i = data.find(magic, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
            if len(hits) > 500:
                break
        if hits:
            any_magic = True
            shown = ", ".join(f"0x{h:08x}" for h in hits[:8])
            more = f" (+{len(hits) - 8} more)" if len(hits) > 8 else ""
            print(f"  {desc:<44} {shown}{more}")
    if not any_magic:
        print("  none found")

    # Architecture heuristics
    print("\n-- architecture heuristics --")
    notes = arm_vector_heuristics(data)
    for line in notes or ["  no obvious vector table at offset 0 (header before code?)"]:
        print(f"  {line}" if not line.startswith("  ") else line)

    # Strings intelligence
    print("\n-- vendor / SDK / sensor hints --")
    strings = list(extract_strings(data, args.min_str))
    lowered = [(off, s, s.lower()) for off, s in strings]
    found_any = False
    for key, desc in VENDOR_HINTS:
        matches = [(off, s) for off, s, sl in lowered if key in sl]
        if matches:
            found_any = True
            off, s = matches[0]
            extra = f" (x{len(matches)})" if len(matches) > 1 else ""
            print(f"  [{key}] {desc}{extra}")
            print(f"      e.g. 0x{off:08x}: {s[:70]!r}")
    joined = "\n".join(s for _, s in strings)
    for pat, maker in SENSOR_PATTERNS:
        for m in sorted(set(re.findall(pat, joined))):
            found_any = True
            print(f"  [sensor] {m} — looks like a {maker} image sensor part number")
    if not found_any:
        print("  nothing matched — strings may be compressed; check high-entropy spans above")

    if args.verbose:
        print("\n-- longest strings --")
        for off, s in sorted(strings, key=lambda t: -len(t[1]))[:40]:
            print(f"  0x{off:08x}: {s[:100]}")

    print(
        "\nNext steps: open in Ghidra with the arch hinted above; if high-entropy"
        "\nspans dominate, identify the compression before disassembling."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
