# Nosh

A development board for the NXP **i.MX RT1176** crossover MCU, modelled closely on the
MIMXRT1170-EVKB (Rev C3) so that EVKB software — in particular `USBHost_t36` and the
M2Radio Wi-Fi/BT library — runs with the same pin assignments.

Schematic capture is done in KiCad 10 (`Kicad/`). PCB layout has not started.

## What is on the board

| Block | Choice | Notes |
|---|---|---|
| MCU | MIMXRT1176DVMAA, MAPBGA-289 | 12-unit symbol generated from `tools/data/*.json`, see below |
| SDRAM | 2 × Winbond W9825G6KH-6 (256 Mb) on SEMC, 32-bit, **64 MB** | same part family and arrangement as the EVKB |
| Flash | Winbond W25Q512JVEIQ, 512 Mb QSPI, 3.3 V | FlexSPI1 port A |
| USB2 (OTG2) | micro-AB **host/OTG** port | the port `USBHost_t36` drives; VBUS via TPS2553 switch, hardware ID gating |
| USB1 (OTG1) | USB-C **device** port | Rd-only UFP (500 mA) |
| M.2 Key E | uSDHC1 @ 1.8 V + LPUART2 | for u-blox MAYA-W1 / NXP IW416; 74AVC8T245 level shifters; TE 2199230-4 socket |
| microSD | uSDHC2 @ 3.3 V | separate bus from the M.2 slot |
| LCD + touch | 40-pin 0.5 mm FPC (Würth 68714014022), MIPI DSI 2 lanes | Rocktech RK055HDMIPI4MA0 (720×1280, HX8394, GT911 touch on LPI2C5), EVKB J48 pinout and GPIO map. No on-board backlight boost or 2.8 V LDO: the adapter board (NXP SPF-39012) generates its own rails and drives its own backlight from the 5 V on pins 39/40 (keep its jumpers J3/J5/J6 at the default 1-2) |
| Audio | Cirrus WM8962 codec on SAI1 + LPI2C5, 3.5 mm line-out and line-in jacks | EVKB U368 circuit on the EVKB pins (GPIO_AD_17..23); headphone-capable line out, IN2L/R line in; no speaker/mic fitted |
| Power | 5 V barrel jack or USB-C → MP2143 3.3 V buck → AMS1117 1.8 V; AP2112K SNVS LDO | EVKB-style rail tree, on-chip DCDC for the core |
| Debug | 10-pin 1.27 mm SWD header, reset / ONOFF / WAKEUP buttons, 2-way boot-mode DIP |

Sheets: `power` (MCU supplies, DCDC, reset/boot), `core` (crystals, USB/MIPI supplies),
`gpio` (GPIO banks, flash, SWD, boot), `usb`, `supply`, `sdram`, `m2`, `sdcard`, `lcd`, `audio`.

## Sourcing / BOM

The board is intended for JLCPCB assembly. Every component carries hidden `LCSC` and `MPN`
fields, and `Kicad/tools/data/lcsc_parts.csv` is the regenerated summary (one line per order
code). Passives are JLCPCB *Basic* parts wherever one exists; everything else is *Extended*.

### MCU availability (read before ordering)

- NXP moved the whole i.MX RT1170 family to rev-B silicon in March 2025 (PCN 202502019I,
  suffix `A` → `B`, fixes erratum ERR052351). The rev-A **MIMXRT1176DVMAA** used here is now
  *Not Recommended for New Designs*, but it is the EVKB part and the only one actually
  obtainable in small quantities (Digi-Key stock; JLCPCB has only a handful).
- **MIMXRT1176DVMAB** (rev B) is pin-identical and is the **accepted alternate**: fit either.
  U1 carries `MPN_Alt` / `LCSC_Alt` (C44999798) fields for it. As of Oct 2026 it has no
  distributor stock and a ~39-week lead time.
- Buy the MCU yourself (Digi-Key/Mouser) and consign it to JLCPCB rather than relying on
  JLCPCB's own stock. Only the 0–95 °C "D" grade is the 1 GHz bin; the industrial C/A grades
  are 800 MHz parts and need a clock-init change if ever fitted.

Other notes: the SDRAM, USB chokes (Murata DLW21HN900SQ2L) and VBUS switch (TI TPS2553DBVR)
were chosen over the EVKB parts specifically for JLCPCB availability; the M.2 socket land
pattern was taken from the EVKB IPC-D-356 data.

## Tools

- `Kicad/tools/gen_rt1176_symbol.py` regenerates the MIMXRT1176DVMAA symbol in
  `Nosh.kicad_sym` from `tools/data/rt1176_pins.json` / `rt1176_mux.json` (annotated pin
  names, 12 units as NXP groups them). Other symbols in the library are preserved.
- Verification used throughout: `kicad-cli sch erc`, `kicad-cli sch export netlist`,
  `kicad-cli sch upgrade --force` (normalises hand-edited files).

The EVKB reference design files (schematic, Allegro netlist, Excel BOM with MPNs, Gerber/IPC-356)
are not part of this repository.
