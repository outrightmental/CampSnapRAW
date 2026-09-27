# Dial behavior specification

## Requirement

> The knob on top of the camera defaults to just ON/OFF — no matter which of
> the "filters" it's set to.

Stock, the top dial selects OFF plus four looks (STD / VTG1 / VTG2 / B&W).
Under this firmware the dial carries **no photographic meaning**:

| Dial position | Stock behavior | This firmware |
|---|---|---|
| OFF | Power off | Power off *(unchanged — this is hardware/PMIC territory; we don't touch it)* |
| STD | JPEG, standard look | **ON — RAW capture** |
| VTG1 | JPEG, vintage 1 | **ON — RAW capture** |
| VTG2 | JPEG, vintage 2 | **ON — RAW capture** |
| B&W | JPEG, black & white | **ON — RAW capture** |

All four ON positions are byte-for-byte identical in behavior. Rotating the
dial while on causes **no** mode change, no beep, no re-init, no hiccup — the
camera just keeps working.

## Why firmware can do this

The dial is read by the SoC (either as GPIOs or as an ADC resistor ladder —
teardown will tell us, see `hardware.md`). Firmware maps the reading to a mode
index and uses it to pick a filter/`.flt` profile. The patch is conceptually
tiny:

```
mode = read_dial_position()      →      mode = MODE_RAW   // constant
```

plus neutralizing any "dial changed" event handler (debounce/notify/beep) so
position changes are ignored entirely rather than re-triggering setup.

The OFF position is expected to gate power at the hardware level (like the
original camera's switch). If it turns out OFF is *soft* (firmware-polled),
we preserve stock OFF handling exactly.

## Implementation checklist (Phase 4)

- [ ] Locate dial read routine (search: ADC reads near mode table, or GPIO
      port reads feeding a 5-way switch/case)
- [ ] Locate the mode/filter table it indexes
- [ ] Patch: constant mode; all filter table entries point to the RAW path
      (belt and suspenders — either patch alone should suffice)
- [ ] Neutralize dial-change interrupt/poll handler side effects
- [ ] Verify: shoot in all four positions → identical RAW output; rotate dial
      mid-session → no interruption; OFF still powers down; power-on works
      from every position
