#!/usr/bin/env python3
"""dng_wrap.py — wrap a raw Bayer sensor dump into a valid DNG.

Takes a bare frame dump (as extracted from the camera's DRAM/SD by future
firmware patches) and produces an uncompressed, standards-compliant DNG that
opens in darktable, RawTherapee, dcraw, Lightroom, etc.

Usage:
    python3 dng_wrap.py frame.raw -o frame.dng -W 4608 -H 3456 \\
        --bpp 10 --pack mipi --cfa RGGB [--black 64] [--white 1023]

Packing formats (--pack):
    mipi     MIPI CSI-2 packed (RAW10: 4px/5B, RAW12: 2px/3B) [needs --bpp 10|12]
    plain16  little-endian 16-bit words holding the sample in low bits
    be16     big-endian 16-bit words
    plain8   one byte per pixel (8-bit sensors / preview taps)

Getting it wrong looks obvious and is easy to iterate:
    - plaid/checkerboard color cast  -> wrong --cfa (4 possibilities, try all)
    - diagonal tearing               -> wrong -W (width/stride)
    - image split or garbage rows    -> wrong --pack or trailing header bytes
      (use --skip N to drop a leading header)

Self-test (builds a synthetic frame and validates the output structure):
    python3 dng_wrap.py --selftest

Stdlib only; uses numpy automatically if installed (much faster). MIT.
"""

import argparse
import struct
import sys
from pathlib import Path

try:
    import numpy as _np
except ImportError:  # pure-python fallback below
    _np = None

# ---------------------------------------------------------------- unpacking

def unpack_mipi10(buf: bytes):
    """MIPI RAW10: groups of 5 bytes -> 4 pixels."""
    usable = len(buf) - (len(buf) % 5)
    buf = buf[:usable]
    if _np is not None:
        b = _np.frombuffer(buf, dtype=_np.uint8).reshape(-1, 5).astype(_np.uint16)
        out = _np.empty((b.shape[0], 4), dtype=_np.uint16)
        for i in range(4):
            out[:, i] = (b[:, i] << 2) | ((b[:, 4] >> (2 * i)) & 0x3)
        return out.reshape(-1)
    out = []
    for g in range(0, usable, 5):
        b0, b1, b2, b3, b4 = buf[g : g + 5]
        out.append((b0 << 2) | (b4 & 0x3))
        out.append((b1 << 2) | ((b4 >> 2) & 0x3))
        out.append((b2 << 2) | ((b4 >> 4) & 0x3))
        out.append((b3 << 2) | ((b4 >> 6) & 0x3))
    return out


def unpack_mipi12(buf: bytes):
    """MIPI RAW12: groups of 3 bytes -> 2 pixels."""
    usable = len(buf) - (len(buf) % 3)
    buf = buf[:usable]
    if _np is not None:
        b = _np.frombuffer(buf, dtype=_np.uint8).reshape(-1, 3).astype(_np.uint16)
        out = _np.empty((b.shape[0], 2), dtype=_np.uint16)
        out[:, 0] = (b[:, 0] << 4) | (b[:, 2] & 0x0F)
        out[:, 1] = (b[:, 1] << 4) | (b[:, 2] >> 4)
        return out.reshape(-1)
    out = []
    for g in range(0, usable, 3):
        b0, b1, b2 = buf[g : g + 3]
        out.append((b0 << 4) | (b2 & 0x0F))
        out.append((b1 << 4) | (b2 >> 4))
    return out


def unpack_plain16(buf: bytes, big_endian=False):
    usable = len(buf) - (len(buf) % 2)
    if _np is not None:
        dt = ">u2" if big_endian else "<u2"
        return _np.frombuffer(buf[:usable], dtype=dt).astype(_np.uint16)
    fmt = ">%dH" % (usable // 2) if big_endian else "<%dH" % (usable // 2)
    return list(struct.unpack(fmt, buf[:usable]))


def unpack_plain8(buf: bytes):
    if _np is not None:
        return _np.frombuffer(buf, dtype=_np.uint8).astype(_np.uint16)
    return list(buf)


def pixels_to_le16(pixels) -> bytes:
    if _np is not None:
        return _np.asarray(pixels, dtype="<u2").tobytes()
    return struct.pack("<%dH" % len(pixels), *pixels)


# ---------------------------------------------------------------- TIFF/DNG

TYPE_BYTE, TYPE_ASCII, TYPE_SHORT, TYPE_LONG, TYPE_SRATIONAL = 1, 2, 3, 4, 10
TYPE_SIZE = {TYPE_BYTE: 1, TYPE_ASCII: 1, TYPE_SHORT: 2, TYPE_LONG: 4, TYPE_SRATIONAL: 8}

CFA_CODE = {"R": 0, "G": 1, "B": 2}


class Entry:
    __slots__ = ("tag", "typ", "count", "data", "off")

    def __init__(self, tag, typ, count, data: bytes):
        self.tag, self.typ, self.count, self.data = tag, typ, count, data
        self.off = None


def e_short(tag, *vals):
    return Entry(tag, TYPE_SHORT, len(vals), struct.pack("<%dH" % len(vals), *vals))


def e_long(tag, *vals):
    return Entry(tag, TYPE_LONG, len(vals), struct.pack("<%dI" % len(vals), *vals))


def e_byte(tag, *vals):
    return Entry(tag, TYPE_BYTE, len(vals), bytes(vals))


def e_ascii(tag, s: str):
    b = s.encode("ascii") + b"\x00"
    return Entry(tag, TYPE_ASCII, len(b), b)


def e_srational(tag, pairs):
    data = b"".join(struct.pack("<ii", n, d) for n, d in pairs)
    return Entry(tag, TYPE_SRATIONAL, len(pairs), data)


def build_dng(pixdata: bytes, width, height, cfa, black, white, model, matrix):
    cfa_bytes = [CFA_CODE[c] for c in cfa]
    entries = [
        e_long(254, 0),                     # NewSubfileType: full-res image
        e_long(256, width),                 # ImageWidth
        e_long(257, height),                # ImageLength
        e_short(258, 16),                   # BitsPerSample
        e_short(259, 1),                    # Compression: none
        e_short(262, 32803),                # Photometric: CFA
        e_ascii(271, "Camp Snap"),          # Make
        e_ascii(272, model),                # Model
        e_long(273, 0),                     # StripOffsets (patched below)
        e_short(274, 1),                    # Orientation
        e_short(277, 1),                    # SamplesPerPixel
        e_long(278, height),                # RowsPerStrip
        e_long(279, len(pixdata)),          # StripByteCounts
        e_short(284, 1),                    # PlanarConfiguration
        e_short(33421, 2, 2),               # CFARepeatPatternDim
        e_byte(33422, *cfa_bytes),          # CFAPattern
        e_byte(50706, 1, 4, 0, 0),          # DNGVersion
        e_ascii(50708, f"Camp Snap {model}"),  # UniqueCameraModel
        e_short(50714, black),              # BlackLevel
        e_long(50717, white),               # WhiteLevel
        e_srational(50721, matrix),         # ColorMatrix1
        e_short(50778, 21),                 # CalibrationIlluminant1: D65
    ]
    entries.sort(key=lambda e: e.tag)

    n = len(entries)
    ifd_off = 8
    ifd_len = 2 + 12 * n + 4
    extra_off = ifd_off + ifd_len

    extra = bytearray()
    cur = extra_off
    for e in entries:
        if len(e.data) > 4:
            if cur % 2:
                extra += b"\x00"
                cur += 1
            e.off = cur
            extra += e.data
            cur += len(e.data)
    if cur % 2:
        extra += b"\x00"
        cur += 1
    data_off = cur

    for e in entries:  # patch StripOffsets now that layout is known
        if e.tag == 273:
            e.data = struct.pack("<I", data_off)

    out = bytearray()
    out += b"II" + struct.pack("<HI", 42, ifd_off)
    out += struct.pack("<H", n)
    for e in entries:
        out += struct.pack("<HHI", e.tag, e.typ, e.count)
        if len(e.data) > 4:
            out += struct.pack("<I", e.off)
        else:
            out += e.data + b"\x00" * (4 - len(e.data))
    out += struct.pack("<I", 0)  # next IFD
    out += extra
    assert len(out) == data_off, (len(out), data_off)
    out += pixdata
    return bytes(out)


# ---------------------------------------------------------------- CLI

def parse_matrix(s):
    vals = [float(x) for x in s.split(",")]
    if len(vals) != 9:
        raise argparse.ArgumentTypeError("matrix needs 9 comma-separated floats")
    return [(int(round(v * 10000)), 10000) for v in vals]


IDENTITY = [(10000, 10000), (0, 1), (0, 1),
            (0, 1), (10000, 10000), (0, 1),
            (0, 1), (0, 1), (10000, 10000)]


def convert(args) -> bytes:
    buf = args.input.read_bytes()
    if args.skip:
        buf = buf[args.skip:]

    if args.pack == "mipi":
        if args.bpp == 10:
            pixels = unpack_mipi10(buf)
        elif args.bpp == 12:
            pixels = unpack_mipi12(buf)
        else:
            sys.exit("--pack mipi requires --bpp 10 or 12")
    elif args.pack == "plain16":
        pixels = unpack_plain16(buf)
    elif args.pack == "be16":
        pixels = unpack_plain16(buf, big_endian=True)
    elif args.pack == "plain8":
        pixels = unpack_plain8(buf)
    else:
        sys.exit(f"unknown pack {args.pack}")

    need = args.width * args.height
    have = len(pixels)
    if have < need:
        sys.exit(f"not enough pixels: need {need}, decoded {have}. "
                 "Wrong -W/-H, --pack, or --bpp?")
    if have > need:
        print(f"note: {have - need} trailing pixels ignored "
              "(padding/stride is normal)", file=sys.stderr)
        pixels = pixels[:need]

    white = args.white if args.white else (1 << args.bpp) - 1
    dng = build_dng(pixels_to_le16(pixels), args.width, args.height,
                    args.cfa, args.black, white, args.model,
                    args.matrix or IDENTITY)
    return dng


def selftest():
    """Build a synthetic gradient frame, wrap it, and re-parse the TIFF."""
    W, H, BPP = 64, 48, 10
    maxv = (1 << BPP) - 1
    pixels = [((x + y) * maxv // (W + H - 2)) for y in range(H) for x in range(W)]
    dng = build_dng(pixels_to_le16(pixels), W, H, "RGGB", 0, maxv,
                    "CS-Pro (selftest)", IDENTITY)

    assert dng[:4] == b"II\x2a\x00", "bad TIFF header"
    (ifd_off,) = struct.unpack_from("<I", dng, 4)
    (count,) = struct.unpack_from("<H", dng, ifd_off)
    tags = {}
    prev_tag = -1
    for i in range(count):
        tag, typ, cnt = struct.unpack_from("<HHI", dng, ifd_off + 2 + 12 * i)
        val_off = ifd_off + 2 + 12 * i + 8
        assert tag > prev_tag, "tags not ascending"
        prev_tag = tag
        tags[tag] = (typ, cnt, val_off)
    for required in (256, 257, 258, 259, 262, 273, 279, 33422, 50706, 50721):
        assert required in tags, f"missing tag {required}"
    (w,) = struct.unpack_from("<I", dng, tags[256][2])
    (h,) = struct.unpack_from("<I", dng, tags[257][2])
    (soff,) = struct.unpack_from("<I", dng, tags[273][2])
    (sbytes,) = struct.unpack_from("<I", dng, tags[279][2])
    assert (w, h) == (W, H)
    assert sbytes == W * H * 2 and soff + sbytes == len(dng)
    first = struct.unpack_from("<H", dng, soff)[0]
    last = struct.unpack_from("<H", dng, soff + sbytes - 2)[0]
    assert first == 0 and last == maxv, (first, last)

    # unpacker round-trips
    ref = [1, 513, 1023, 0]
    packed10 = bytes([ref[0] >> 2, ref[1] >> 2, ref[2] >> 2, ref[3] >> 2,
                      (ref[0] & 3) | ((ref[1] & 3) << 2)
                      | ((ref[2] & 3) << 4) | ((ref[3] & 3) << 6)])
    assert list(unpack_mipi10(packed10)) == ref
    ref12 = [4095, 256]
    packed12 = bytes([ref12[0] >> 4, ref12[1] >> 4,
                      (ref12[0] & 0xF) | ((ref12[1] & 0xF) << 4)])
    assert list(unpack_mipi12(packed12)) == ref12

    print(f"selftest OK — {len(dng)} byte DNG, {count} IFD entries, "
          f"strip @0x{soff:x}, numpy={'yes' if _np else 'no'}")
    return dng


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("-W", "--width", type=int)
    ap.add_argument("-H", "--height", type=int)
    ap.add_argument("--bpp", type=int, default=10, choices=(8, 10, 12, 14, 16))
    ap.add_argument("--pack", default="mipi",
                    choices=("mipi", "plain16", "be16", "plain8"))
    ap.add_argument("--cfa", default="RGGB",
                    choices=("RGGB", "GRBG", "GBRG", "BGGR"))
    ap.add_argument("--black", type=int, default=0)
    ap.add_argument("--white", type=int, default=0, help="default: 2^bpp - 1")
    ap.add_argument("--skip", type=int, default=0,
                    help="skip N leading bytes (frame header)")
    ap.add_argument("--model", default="CS-Pro")
    ap.add_argument("--matrix", type=parse_matrix, default=None,
                    help="ColorMatrix1: 9 comma-separated floats (XYZ->cam). "
                         "Default identity = flat color, fix in post until "
                         "the sensor is calibrated")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return 0
    if not (args.input and args.output and args.width and args.height):
        ap.error("input, -o, -W and -H are required (or use --selftest)")

    dng = convert(args)
    args.output.write_bytes(dng)
    print(f"wrote {args.output} ({len(dng)/1024/1024:.1f} MiB, "
          f"{args.width}x{args.height}, {args.cfa}, "
          f"black={args.black}, white={args.white or (1 << args.bpp) - 1})")
    print("open it in darktable/RawTherapee; if colors look plaid, "
          "try the other --cfa values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
