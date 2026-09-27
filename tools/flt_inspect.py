#!/usr/bin/env python3
"""flt_inspect.py — analyze and diff Camp Snap .flt filter files.

The .flt format is undocumented. This tool helps reverse it: report size,
entropy, header bytes, and check whether the payload matches common LUT
geometries. In diff mode, show exactly which byte ranges change between two
looks — those ranges are the color pipeline parameters.

Usage:
    python3 flt_inspect.py std.flt              # analyze one file
    python3 flt_inspect.py std.flt vtg1.flt     # analyze + structural diff

Stdlib only. MIT.
"""

import argparse
import hashlib
import math
import sys
from pathlib import Path


def shannon(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


def hexdump(data: bytes, base: int = 0, rows: int = 4) -> str:
    out = []
    for r in range(rows):
        off = r * 16
        chunk = data[off : off + 16]
        if not chunk:
            break
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asci = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
        out.append(f"  {base + off:08x}  {hexs:<47}  {asci}")
    return "\n".join(out)


def lut_guesses(n: int):
    g = []
    for s in (2, 4, 8, 9, 16, 17, 32, 33, 64, 65):
        if n == s ** 3 * 3:
            g.append(f"{s}x{s}x{s} RGB 3D LUT, 8-bit ({n} B)")
        if n == s ** 3 * 3 * 2:
            g.append(f"{s}x{s}x{s} RGB 3D LUT, 16-bit ({n} B)")
    for s in (256, 512, 1024, 4096):
        if n == s * 3:
            g.append(f"{s}-entry 1D RGB LUT, 8-bit")
        if n == s * 3 * 2:
            g.append(f"{s}-entry 1D RGB LUT, 16-bit")
        if n == s:
            g.append(f"{s}-entry single-channel 1D LUT, 8-bit")
    # header + payload combos
    for hdr in (16, 32, 64, 128, 256, 512):
        body = n - hdr
        if body <= 0:
            continue
        for s in (9, 16, 17, 32, 33):
            if body == s ** 3 * 3:
                g.append(f"{hdr}-byte header + {s}^3 RGB 3D LUT (8-bit)")
        if body == 256 * 3:
            g.append(f"{hdr}-byte header + 256-entry 1D RGB LUT")
    return g


def analyze(path: Path) -> bytes:
    data = path.read_bytes()
    print(f"== {path.name} ==")
    print(f"size   : {len(data)} bytes")
    print(f"sha256 : {hashlib.sha256(data).hexdigest()}")
    print(f"entropy: {shannon(data):.3f} bits/byte "
          "(<4: tables/curves likely; >7.5: compressed/encrypted)")
    print("first 64 bytes:")
    print(hexdump(data[:64]))
    guesses = lut_guesses(len(data))
    if guesses:
        print("size matches known LUT geometry:")
        for g in guesses:
            print(f"  - {g}")
    else:
        print("size matches no plain LUT geometry — likely structured "
              "(header + sections) or register blob")
    print()
    return data


def diff(a: bytes, b: bytes, name_a: str, name_b: str, gap: int = 16):
    print(f"== diff {name_a} vs {name_b} ==")
    if len(a) != len(b):
        print(f"sizes differ: {len(a)} vs {len(b)} — comparing common prefix")
    n = min(len(a), len(b))
    ranges = []
    i = 0
    while i < n:
        if a[i] != b[i]:
            start = i
            last = i
            while i < n:
                if a[i] != b[i]:
                    last = i
                    i += 1
                elif i - last <= gap:
                    i += 1
                else:
                    break
            ranges.append((start, last + 1))
        else:
            i += 1
    differing = sum(1 for i in range(n) if a[i] != b[i])
    print(f"{differing}/{n} bytes differ ({100 * differing / n:.1f}%) "
          f"in {len(ranges)} region(s):")
    for start, end in ranges[:40]:
        print(f"  0x{start:06x} - 0x{end:06x}  ({end - start} B)")
        print(f"    {name_a}: {a[start:min(end, start + 16)].hex(' ')}")
        print(f"    {name_b}: {b[start:min(end, start + 16)].hex(' ')}")
    if len(ranges) > 40:
        print(f"  ... and {len(ranges) - 40} more regions")
    if ranges:
        print("\nInterpretation tips:")
        print("  - identical header + differing tail  -> header is metadata, tail is the look")
        print("  - smooth byte ramps in diff regions  -> tone curves / LUT entries")
        print("  - few scattered small diffs          -> register/parameter blob")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", type=Path, help="one .flt to analyze, two to diff")
    args = ap.parse_args()
    if len(args.files) > 2:
        ap.error("pass one or two files")
    blobs = [analyze(p) for p in args.files]
    if len(blobs) == 2:
        diff(blobs[0], blobs[1], args.files[0].name, args.files[1].name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
