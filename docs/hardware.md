# CS-Pro hardware — what we know, what we need

## Confirmed from public sources

| Item | Status |
|---|---|
| Sensor | 16 MP, exact model **unknown**. Small-format (smartphone-class) module, fixed-focus lens |
| Lens | Fixed, 37 mm front filter thread |
| Flash | Xenon tube (not LED) — implies a charge/trigger circuit worth avoiding during teardown (caps hold high voltage!) |
| SoC | **Unknown.** Confirmed *different* from the original Camp Snap's chip (founder statement to press when old `.flt` files didn't work on the Pro) |
| Original Camp Snap SoC, for contrast | iCatchtek (USB descriptor `04fc:0171`, "Icatchtek Co Ltd", ARM-based). CS-Pro is NOT this — but iCatch has newer parts, so a newer iCatch chip is a live hypothesis |
| Filter files | Community `.flt` color profiles, loaded from card root as `std.flt`, `vtg1.flt`, `vtg2.flt`, `bw.flt` — one per dial position |
| Storage | Removable microSD/TF card, camera enumerates as USB mass storage |
| Controls | Top dial: OFF + four filter positions. Shutter button. Flash control. |

## Teardown checklist (the most valuable contribution right now)

⚠️ **Xenon flash warning:** the flash capacitor can hold hundreds of volts
long after power-off. Don't poke the flash board; discharge or leave it alone.

1. Remove the card and battery. Photograph every step so reassembly is easy.
2. **Main SoC**: sharp, well-lit photo of the largest chip's laser markings.
   If there's thermal paste/glue, note it but don't scrape blindly.
3. **Image sensor module**: markings on the FPC ribbon or module housing.
4. **Flash memory**: look for an 8-pin SOIC (SPI NOR, typical: Winbond `25Qxx`,
   GigaDevice `GD25`, XMC, etc.) or a larger NAND/eMMC. Photo + marking.
5. **Dial**: how many contacts run from the dial to the board? Follow the
   traces. A resistor ladder into one pin = ADC read; multiple pins = GPIO.
6. **Debug pads**: look for 3-4 unpopulated pads in a row near the SoC
   (UART TX/RX/GND) or labeled test points (`TX`, `RX`, `TP1`…). Photo.
7. Battery model/capacity, and any other IC markings for completeness.

Open an issue tagged `hw-intel` with the photos.

## SoC identification shortcuts (no teardown)

- Plug into a computer and record the **USB VID:PID and descriptor strings**
  (`lsusb -v` on Linux, System Information on macOS). Vendor IDs often name
  the SoC maker outright — that's how the original was pinned to iCatchtek.
- Check the EXIF of a stock JPEG (`exiftool photo.jpg`). SDK default fields
  (Make, Software, processing tags) frequently leak the chip vendor's SDK name.
- If a firmware update file ever ships: `tools/fw_identify.py` will hunt for
  vendor strings automatically.

## Likely usual suspects

Cameras in this class ship SoCs from: iCatch/Sunplus, Sonix, JieLi, Anyka,
Buildwin, Goke, Generalplus, Novatek. Each has a known SDK style, and several
have existing hobbyist RE communities — identifying the vendor instantly tells
us how hard the rest of this project will be.
