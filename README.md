# Nosh

A development board for the NXP **i.MX RT1176** crossover MCU, modelled closely on the
MIMXRT1170-EVKB (Rev C3) so that EVKB software — `USBHost_t36`, the M2Radio Wi-Fi/BT
library, `MipiDisplay` and the NXP SDK board files — runs with the same pin assignments.
Where Nosh departs from the EVKB it is for JLCPCB availability or because an EVKB block was
not wanted; every departure is listed below.

**Status:** schematic capture complete for the blocks listed (KiCad 10, `Kicad/`). PCB layout
has not started. Full-hierarchy ERC is clean apart from the expected unconnected MCU balls
(68) and 8 undriven-input notes on open pins.

## What is on the board

| Block | Choice | Notes |
|---|---|---|
| MCU | MIMXRT1176DVMAA (rev-B DVMAB accepted alternate), MAPBGA-289 | 12-unit symbol generated from `tools/data/*.json` |
| SDRAM | 2 × Winbond W9825G6KH-6 (256 Mb) on SEMC, 32-bit, **64 MB** | same part family and arrangement as the EVKB (13 row × 9 column) |
| Flash | Winbond W25Q512JVEIQ, 512 Mb QSPI, 3.3 V | FlexSPI1 port A (GPIO_SD_B2_06..11) |
| USB2 (OTG2) | micro-AB **host/OTG** port | the port `USBHost_t36` drives; TPS2553 VBUS switch (~1.1 A) with hardware ID gating, RClamp0854P ESD |
| USB1 (OTG1) | USB-C **device** port | Rd-only UFP (500 mA), RClamp0854P ESD |
| M.2 Key E | uSDHC1 @ 1.8 V + LPUART2 | for u-blox MAYA-W1 / NXP IW416; 74AVC8T245 level shifters; TE 2199230-4 socket (EVKB part) |
| microSD | uSDHC2 @ 3.3 V | its own bus — the EVKB shares one with the M.2 slot |
| LCD + touch | 40-pin 0.5 mm FPC (Würth 68714014022), MIPI DSI 2 lanes | Rocktech RK055HDMIPI4MA0 (720×1280, HX8394, GT911 touch on LPI2C5), EVKB J48 pinout and GPIO map |
| Audio | Cirrus WM8962 codec on SAI1 + LPI2C5, 3.5 mm line-out and line-in jacks | EVKB U368 circuit on the EVKB pins; headphone-capable line out, IN2L/R line in |
| Power | 5 V barrel jack or USB-C → MP2143 3.3 V buck → AMS1117 1.8 V; AP2112K SNVS LDO | EVKB-style rail tree, on-chip DCDC for the core; 2 A polyfuse, reverse-polarity diode |
| Debug | 10-pin 1.27 mm SWD/JTAG header, reset / ONOFF / WAKEUP buttons, 2-way boot-mode DIP, 72 test points | JTAG on GPIO_LPSR_10..15, VTref = NVCC_LPSR (3.3 V); LPUART1 console on TP62/TP63 |

Sheets: `power` (MCU supplies, DCDC, reset/boot), `core` (crystals, USB/MIPI supplies),
`gpio` (GPIO banks, flash, SWD, boot), `usb`, `supply`, `sdram`, `m2`, `sdcard`, `lcd`, `audio`,
`testpoints`.

## Pin map (for software)

All assignments are the EVKB's unless marked.

| Function | RT1176 pads / balls |
|---|---|
| USB host (OTG2) | USB2_DP/DN C17/C16, VBUS sense D16; `USB_OTG2_ID` GPIO_AD_08, `USB_OTG2_OC` GPIO_AD_06 |
| USB device (OTG1) | USB1_DP/DN E17/E16, VBUS sense D17 |
| M.2 SDIO (uSDHC1, 1.8 V) | GPIO_SD_B1_00..05; `WIFI_RST_B` GPIO_AD_16, `WL_RST_B` GPIO_AD_31, `BT_RST_B` GPIO_AD_15, `WL_DEV_WAKE` GPIO_AD_07, `BT_DEV_WAKE` GPIO_AD_28, `BT_WAKE_B` GPIO_AD_27, `WIFI_WAKE_B` GPIO_AD_29 |
| BT HCI UART (LPUART2) | GPIO_DISP_B2_10..13 |
| microSD (uSDHC2, 3.3 V) — *Nosh* | GPIO_SD_B2_00..05; `SD_CD_B` GPIO_AD_34, `SD_PWREN_B` GPIO_AD_35 |
| QSPI flash (FlexSPI1 A) | GPIO_SD_B2_06..11 |
| SDRAM (SEMC) | GPIO_EMC_B1/B2 |
| LCD (MIPI DSI) | D0 A8/B8, D1 A10/B10, CLK A9/B9; reset GPIO_AD_02, backlight GPIO_AD_30, panel power GPIO_DISP_B2_15, TE GPIO_AD_05 |
| Touch + codec I2C (LPI2C5) | GPIO_LPSR_04 SDA / GPIO_LPSR_05 SCL; touch INT GPIO_AD_00, touch RST GPIO_AD_01 |
| Audio (SAI1) | MCLK GPIO_AD_17, RX_SYNC/RX_BCLK GPIO_AD_18/19 (DNP links), RXD0 GPIO_AD_20, TXD0 GPIO_AD_21, TX_BCLK GPIO_AD_22, TX_SYNC GPIO_AD_23 |
| Boot mode | GPIO_LPSR_02/03 (DIP switch), internal boot from FlexSPI1 NOR by default |
| Debug console (LPUART1) — *Nosh: test points only* | GPIO_AD_24 TXD / GPIO_AD_25 RXD on TP62 / TP63 (no header fitted) |

## Differences from the MIMXRT1170-EVKB

| Block | EVKB | Nosh | Why |
|---|---|---|---|
| SDRAM | 2 × W9825G6KH-5I | 2 × W9825G6KH-6 | -5I not stocked; -6 is the 166 MHz commercial bin |
| USB ports | two micro-AB OTG ports | micro-AB host + USB-C device | one port is enough for the host library; USB-C for programming |
| USB VBUS switch | NX5P3090UK (0.4 mm WLCSP) | TPS2553DBVR (SOT-23-6), RILIM 22 k ≈ 1.1 A | no stock, hard package; same EN/FAULT/ILIM topology |
| SD card bus | shared with the M.2 slot | separate uSDHC2 | independent Wi-Fi and SD |
| QSPI flash | W25Q512NWEIQ (1.8 V) | W25Q512JVEIQ (3.3 V) | NVCC_SD2 at 3.3 V keeps the SD bus simple |
| LCD backlight / 2.8 V | on-board boost and LDO | none | the RK055HDMIPI4MA0 adapter (NXP SPF-39012) generates its own rails and drives its own backlight from the 5 V on FPC pins 39/40 — keep its jumpers J3/J5/J6 at the default 1-2 |
| LCD TE | 74AVC8T245 level shifter to GPIO_AD_05 | DNP 0 R | DSI video mode never uses TE; add a shifter if needed |
| Audio | codec + speaker outputs + electret mic + headphone jack with detect | codec + line out + line in | no mic/speakers wanted; the CUI jack's switch would bias the ground-referenced HPOUT, so no jack detect |
| Not fitted at all | Ethernet (1G + 100M), CAN, camera, Arduino headers, PMIC, LPC55 debug probe, PDM mics, accelerometer | — | use an external SWD probe |

## Sourcing / BOM

The board is intended for JLCPCB assembly. Every component carries hidden `LCSC` and `MPN`
fields (U1 also `MPN_Alt`/`LCSC_Alt`), and `Kicad/tools/data/lcsc_parts.csv` is the generated
summary: one line per order code with quantity and references, DNP parts marked. Current count:
262 fitted parts on 61 order codes, 21 of them JLCPCB *Basic*. Regenerate it with

```bash
python3 Kicad/tools/lcsc_table.py
```

### MCU availability (read before ordering)

- NXP moved the whole i.MX RT1170 family to rev-B silicon in March 2025 (PCN 202502019I,
  suffix `A` → `B`, fixes erratum ERR052351). The rev-A **MIMXRT1176DVMAA** used here is now
  *Not Recommended for New Designs*, but it is the EVKB part and the only one actually
  obtainable in small quantities (Digi-Key stock; JLCPCB has only a handful).
- **MIMXRT1176DVMAB** (rev B) is pin-identical and is the **accepted alternate**: fit either.
  As of Oct 2026 it has no distributor stock and a ~39-week lead time.
- Buy the MCU yourself (Digi-Key/Mouser) and consign it to JLCPCB rather than relying on
  JLCPCB's own stock. Only the 0–95 °C "D" grade is the 1 GHz bin; the industrial C/A grades
  are 800 MHz parts and need a clock-init change if ever fitted.

### Other parts worth checking before an order

| Part | JLCPCB | Oct 2026 stock | Alternative |
|---|---|---|---|
| WM8962BECSN/R codec | C5184531 | ~300 | WM8904 (QFN, NXP SDK driver) needs a new symbol/footprint |
| Würth 68714014022 LCD FPC | C6264899 | ~75 | any 40-pin 0.5 mm top-contact ZIF with the same land pattern |
| CUI SJ-3523-SMT jacks | C4991872 | ~800 | — |
| TE 2199230-4 M.2 socket | C2977809 | ~5 k | — |

Fine-pitch note: the MCU is 0.8 mm BGA, the codec 0.5 mm W-CSP; everything else is 0.4 mm
QFN or coarser.

## Flashing and debugging

The RT1176 has no internal flash: the ROM boots from the W25Q512 on FlexSPI1, so "flashing"
means writing the QSPI NOR through the MCU. A debug tool needs an RT1170 FlexSPI flash
algorithm (it loads a small loader into OCRAM that uses the ROM's FlexSPI API); pyOCD gets it
from the NXP CMSIS pack, J-Link has it built in. Images must start with the FCB + IVT + boot
data at `0x30000000` — any SDK `flexspi_nor` link target does this, and the EVKB FCB (written
for the 1.8 V W25Q512NW) drives our 3.3 V W25Q512JV unchanged (same command set, same QE bit).

### SWD header J1 (standard Cortex 10-pin, 1.27 mm)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | VTref = NVCC_LPSR (3.3 V) | 2 | SWDIO (GPIO_LPSR_15) |
| 3 | GND | 4 | SWCLK (GPIO_LPSR_14) |
| 5 | GND | 6 | SWO (GPIO_LPSR_11) |
| 7 | key | 8 | TDI (GPIO_LPSR_12) |
| 9 | GND | 10 | nRESET → POR_B via D1 |

JTAG_MOD is pulled low (SWD mode) and the debug domain is 3.3 V, so any 3.3 V SWD probe
connects directly.

### Probes

- Any **CMSIS-DAP** probe: NXP MCU-Link (the EVKB's own probe as a dongle; also works with
  LinkServer/MCUXpresso), Raspberry Pi Debug Probe (CMSIS-DAP v2, fast), Atmel-ICE (its EDBG
  firmware exposes a standard CMSIS-DAP interface; use the 10-pin "SAM" header), or a SAMD21
  board such as a MKR ZERO running [free-dap](https://github.com/ataradov/free-dap) (slow HID
  probe, fine for bring-up; wire SWCLK, SWDIO, GND and optionally nRESET).
- **J-Link**: `-device MIMXRT1176xxxA_M7 -if SWD`; the most robust RT1170 flash loader.
- AVR-only programmers (AVRISP mkII, STK500, UPDI) cannot do SWD.

### pyOCD (generic CMSIS-DAP probes)

```bash
pip install pyocd
pyocd pack install mimxrt1176          # NXP MIMXRT1176 DFP incl. the FlexSPI NOR algorithm
pyocd list --targets | grep -i 1176    # pick the ..._cm7 target the pack installed
pyocd flash -t <target> -f 4m app.elf  # or app.bin -a 0x30000000
pyocd gdbserver -t <target>
```

If the flash is blank or holds a bad image the ROM may sit in its serial-downloader loop; add
`--connect under-reset` if a plain attach fails. OpenOCD has no mainline RT1170 FlexSPI
driver, so pyOCD is the practical choice for generic probes.

### No probe: the ROM serial downloader over USB-C

Set the boot DIP to `01` (serial downloader) and plug the USB-C port — it is USB1/OTG1, the
port the RT1170 ROM uses for SDP. Then with NXP's SPSDK:

```bash
pip install spsdk
nxpdevscan                                                   # ROM enumerates as 1fc9:013d
blhost -u 0x1fc9,0x013d -- load-image ivt_flashloader.bin    # from the RT1170 SDK / SPT package
blhost -u 0x15a2,0x0073 -- fill-memory 0x2000 4 0xC0000007   # QuadSPI NOR config option
blhost -u 0x15a2,0x0073 -- configure-memory 9 0x2000
blhost -u 0x15a2,0x0073 -- flash-erase-region 0x30000000 0x100000 9
blhost -u 0x15a2,0x0073 -- write-memory 0x30000000 app.bin
```

NXP's MCUXpresso Secure Provisioning Tool does the same through a GUI. This is also the
recovery path if a bad image ever makes an SWD attach awkward.

### Test points

The `testpoints` sheet carries 72 test points, each a global label onto an existing net. They are
bare copper pads (KiCad `TestPoint` footprints, flagged exclude-from-BOM / exclude-from-POS and
`in_bom = no` on the symbols), so they add nothing to the JLCPCB order.

| Refs | Group | Nets |
|---|---|---|
| TP1–TP6 | Ground | GND; 2.0 mm plated holes, solder a wire loop for the scope ground lead |
| TP7–TP21 | Supply rails | DC_IN_F, +5V, +3V3, +1V8, VLDO_3V3, VSD_3V3, WL_3V3, SDRAM_3V3, CODEC_1V8, VMIDC, LCD_5V, LCD_IOVCC_1V8, CTP_3V3, USB1_VBUS, USB2_VBUS |
| TP22–TP35 | MCU power domains | DCDC_IN, DCDC_DIG, DCDC_ANA, VDD_SOC_IN, VDDA_1P8, VDD_SNVS_IN, VDD_LPSR_IN, NVCC_LPSR, NVCC_GPIO, NVCC_SD1, NVCC_SD2, NVCC_EMC1, VDD_USB_3P3, VDDA_ADC_3P3 |
| TP36–TP49 | Reset / boot / power control | POR_B, ONOFF, WAKEUP, PMIC_ON_REQ, PMIC_STBY_REQ, BOOT_MODE0, BOOT_MODE1, DCDC_PSWITCH, DCDC_MODE, BUCK_EN, OTG2_VBUS_EN, USB_OTG2_OC, SD_PWREN_B, SD_CD_B |
| TP50–TP61 | Peripheral control (MCU side, 3.3 V) | LCM_PWR_EN, BACKLIGHT_CTL, LCD_RST_B, LCD_TE, CTP_RST_B, CTP_INT, WL_RST_B, BT_RST_B, WIFI_WAKE_B, BT_WAKE_B, WL_DEV_WAKE, BT_DEV_WAKE |
| TP62–TP72 | Buses | LPUART1_TXD / LPUART1_RXD (TP62 / TP63), LPI2C5_SDA / SCL, SAI1_MCLK, SAI1_TX_BCLK, SAI1_TX_SYNC, SAI1_TXD0, SAI1_RXD0, BT_UART_TXD / RXD |

TP62/TP63 are the only connection to LPUART1 (GPIO_AD_24/25, the SDK's default debug console,
3.3 V): solder wires or a 3-pin header there, plus a ground, for a serial console. Nothing is
probed on the SDRAM, FlexSPI, USB data, MIPI DSI or crystal nets, where a pad stub would degrade
the signal; SWD/SWO are on J1.

## Repository layout

```
Kicad/
  Nosh.kicad_pro / Nosh.kicad_sch        project and root sheet (A3, one block per sub-sheet)
  power core gpio usb supply sdram m2 sdcard lcd audio testpoints .kicad_sch
  Nosh.kicad_sym                         project symbols (MCU, flash, SDRAM, codec, sockets, …)
  Nosh.pretty/                           project footprints:
    bga289_0p8_14x14_1p52mm              MCU (from the EVKB footprint)
    slp1616p6                            RClamp0854P
    M2_KeyE_67pin_RA                     TE 2199230-4 — pads from the EVKB IPC-D-356 data, pegs/tabs from the TE drawing
    FPC40_0p5_Wuerth_68714014022         LCD FPC — EVKB IPC-D-356 land (= Würth recommended pattern)
    L_CommonModeChoke_Murata_DLW21       USB chokes — EVKB IPC-D-356 land
    WCSP-49_3.6x4.0mm_P0.5mm             WM8962 — EVKB IPC-D-356 ball map + datasheet outline
  tools/
    gen_rt1176_symbol.py                 regenerates the MIMXRT1176DVMAA symbol from data/rt1176_{pins,mux}.json
    lcsc_table.py                        regenerates data/lcsc_parts.csv from the schematic fields
    data/                                pin/mux tables, lcsc_parts.csv
```

## Working on the schematic

- Global labels carry every net between sheets; power rails use the KiCad power symbols plus
  `PWR_FLAG`s on passively fed rails. Sheet notes cite the EVKB reference designators for each
  sub-circuit, so the EVKB schematic is the place to look for intent.
- Hand-edited files are normalised with `kicad-cli sch upgrade --force` /
  `kicad-cli sym upgrade --force` / `kicad-cli fp upgrade --force`; check with
  `kicad-cli sch erc --severity-all` and `kicad-cli sch export netlist`.
- The EVKB reference design files (schematic, Allegro netlist, Excel BOM with MPNs,
  Gerber/IPC-356) and the part datasheets are not part of this repository.
