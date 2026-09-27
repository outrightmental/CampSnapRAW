# Getting RAW out of a JPEG-only camera

## The pipeline (every camera in this class)

```
CMOS sensor ──MIPI/DVP──▶ [DRAM: raw Bayer frame] ──▶ ISP ──▶ [YUV frame] ──▶ JPEG encoder ──▶ FAT write
                                    ▲                  │
                                    │                  ├─ demosaic, white balance,
                              THIS is what             ├─ color matrix, gamma,
                              we want on the           ├─ filter look (.flt),
                              SD card                  └─ sharpen, denoise
```

The raw Bayer frame **must** exist in DRAM between sensor readout and ISP
processing (on some SoCs the ISP streams inline, but virtually all support a
raw-capture/bypass DMA mode, because vendors need it for sensor bring-up and
tuning). Our job:

1. Find where capture is triggered in firmware (shutter ISR → capture task).
2. Find the DMA target address + stride for the raw frame, and its pixel
   format (bit depth, packing, CFA order).
3. Insert a call to the firmware's own FAT write routines to save that buffer
   as `IMG_NNNN.RAW` before it's recycled.
4. Grab exposure/gain from sensor registers into a tiny sidecar if reachable.

This is exactly the approach CHDK used on Canon: the DSP was already producing
raw internally; CHDK just wrote the buffer out.

## What we need to learn from RE (per Phase 2)

- [ ] Sensor resolution as configured (16 MP ≈ 4608×3456; confirm actual)
- [ ] Readout bit depth (10-bit is most likely; 12-bit possible)
- [ ] Packing in DRAM: MIPI-packed (10-bit: 4 px/5 B, 12-bit: 2 px/3 B) vs
      unpacked 16-bit words
- [ ] CFA order (RGGB/GRBG/GBRG/BGGR) — also verifiable empirically later by
      shooting a red object and checking channel positions
- [ ] Black level (optical-black rows or register default)
- [ ] Whether a vendor "raw dump" debug mode already exists (many SDKs have
      one behind a config flag — the cheapest possible win)

## Development order

**Step 1 — dump anything.** Even a single raw frame obtained by any means
(debug mode, RAM dump over USB/UART, hacked-in write) proves the pixel format.

**Step 2 — develop on PC.** `tools/dng_wrap.py` wraps a `.RAW` dump into a
standards-compliant DNG that darktable/RawTherapee/Lightroom can open. Wrong
CFA guess → plaid colors; wrong width → diagonal tearing. Both are obvious and
quickly fixed by iterating the flags.

**Step 3 — make it a firmware feature.** Patch the capture path to always
write RAW (see [dial-behavior.md](dial-behavior.md) — no modes, no filters).
Skip the JPEG encode if it buys shutter speed/battery, or keep it as RAW+JPEG
if free.

**Step 4 — in-camera DNG (stretch).** The DNG header for a fixed sensor is
~constant; prepending it in-firmware is cheap once Step 3 is stable.

## Constraints to respect

- **Write size:** 16 MP × 10-bit packed ≈ 20 MB/frame (vs ~4-6 MB JPEG).
  Shot-to-shot time will grow; card speed matters. Document real numbers.
- **Buffer lifetime:** the raw buffer may be reused for the next preview frame;
  the write must finish (or the buffer be copied) first.
- **Xenon flash timing:** don't add latency between metering and trigger.
- **Power:** longer writes = more battery per shot. Measure.
