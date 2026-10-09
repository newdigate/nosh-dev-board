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
| MCU | MIMXRT1176DVMAA (rev-B DVMAB accepted alternate), MAPBGA-289 | 12-unit symbol generated from `tools/data/*.json`; KiCad stock footprint `Package_BGA:MAPBGA-289_14x14mm_Layout17x17_P0.8mm` (0.32 mm pads, EVKB uses 0.33 mm) |
| SDRAM | 2 × Alliance AS4C32M16SB-6TIN (512 Mb) on SEMC, 32-bit, **128 MB** | same JEDEC x16 TSOP-54 footprint and arrangement as the EVKB; 13 row × 10 column, so the firmware SEMC setup changes: 10 column bits and 128 MB on chip select 0, see "SDRAM configuration" below |
| Flash | Winbond W25Q512JVEIQ, 512 Mb QSPI, 3.3 V | FlexSPI1 port A (GPIO_SD_B2_06..11) |
| USB2 (OTG2) | micro-AB **host/OTG** port | the port `USBHost_t36` drives; TPS2553 VBUS switch (~1.1 A) with hardware ID gating, RClamp0854P ESD |
| USB1 (OTG1) | USB-C **device** port | Rd-only UFP (500 mA), RClamp0854P ESD |
| M.2 Key E | uSDHC1 @ 1.8 V + LPUART2 | for u-blox MAYA-W1 / NXP IW416; 74AVC8T245 level shifters; TE 2199230-4 socket (EVKB part); retention nut H5, M2.5 SMT 2 mm (EVKB BH1) |
| microSD | uSDHC2 @ 3.3 V | its own bus — the EVKB shares one with the M.2 slot |
| LCD + touch | 40-pin 0.5 mm FPC (Würth 68714014022), MIPI DSI 2 lanes | Rocktech RK055HDMIPI4MA0 (720×1280, HX8394, GT911 touch on LPI2C5), EVKB J48 pinout and GPIO map |
| Audio | NXP SGTL5000 codec (QFN-20) on SAI1 + LPI2C5, 3.5 mm line-out and line-in jacks | the Teensy Audio Shield codec: Teensy Audio library `AudioControlSGTL5000` and the NXP SDK `sgtl5000` driver both apply; I2C 0x0A; same SAI1 pins as the EVKB codec |
| Power | 5 V barrel jack or USB-C → MP2143 3.3 V buck → AMS1117 1.8 V; AP2112K SNVS LDO | EVKB-style rail tree, on-chip DCDC for the core; 3 A polyfuse, SS54 reverse-polarity diode, jack rated 8 A; red power LED on +3V3 |
| Debug | 10-pin 1.27 mm SWD/JTAG header, reset / ONOFF / WAKEUP buttons, 2-way boot-mode DIP, user LED on GPIO_AD_04, 3-pin debug UART header J11, 72 test points | JTAG on GPIO_LPSR_10..15, VTref = NVCC_LPSR (3.3 V); LPUART1 console on J11, J10 pins 5/6 and TP62/TP63 |
| Expansion | 2×10 2.54 mm header J10 | LPUART1 console, LPI2C5, LPSPI3, FLEXCAN3 / LPUART12 pins, 4 ADC / PWM pins, 1 PWM pin, +3V3, +5V, 3 × GND; see [Expansion header J10](#expansion-header-j10) |
| Mechanical | board outline = the RK055HDMIPI4MA0 adapter outline; 4 × M3 mounting holes H1–H4 on the adapter's standoff positions; 6 fiducials, FID1–FID3 on the top side and FID4–FID6 on the bottom for the bottom-side assembly pass | 3.53 mm plated holes with 5.6 mm GND pads (NXP's .635" M3 standoff land, as on the EVKB); hole coordinates from the adapter design files or measurement before layout |

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
| Boot mode | GPIO_LPSR_02/03 (DIP switch, 100 k pull-downs); BOOT_CFG pins GPIO_DISP_B1_06..11 / GPIO_DISP_B2_00..05 pulled down (100 k), so internal boot is from FlexSPI1 QSPI NOR |
| Debug console (LPUART1) | GPIO_AD_24 TXD / GPIO_AD_25 RXD on J11 (1 GND, 2 TXD, 3 RXD), J10 pins 5 / 6 and TP62 / TP63 |
| Expansion SPI (LPSPI3) — *Nosh* | SCK GPIO_DISP_B1_04, SOUT GPIO_DISP_B1_06, SIN GPIO_DISP_B1_05, CS GPIO_DISP_B1_03 (GPIO-driven) |
| User LED | GPIO_AD_04 (GPIO9_IO03, the SDK's BOARD_USER_LED), high = on; direct drive, 1 k series, red 0603 (the EVKB buffers it with a BC817) |

## Expansion header J10

2 × 10, 2.54 mm pin header (hanxia HX PZ2.54-2x10P ZZ, JLCPCB C42372518), fitted by JLCPCB's
through-hole assembly like the other THT connectors. All signals are **3.3 V and not 5 V tolerant**.

| Pins (odd / even) | Signals | MCU pads | Other functions on these pins |
|---|---|---|---|
| 1 / 2 | +3V3 / +5V | — | +3V3 is the main rail, off while the SoC is powered down by ONOFF; +5V is the diode-OR'd input rail |
| 3 / 4 | GND / GND | — | |
| 5 / 6 | LPUART1_TXD / LPUART1_RXD | GPIO_AD_24 / GPIO_AD_25 | SDK debug console; FLEXPWM2_PWM0_A / B, ADC2_CH6A / B, LPI2C4 |
| 7 / 8 | LPI2C5_SCL / LPI2C5_SDA | GPIO_LPSR_05 / GPIO_LPSR_04 | shared with the touch panel and the codec, 2.2 k pull-ups fitted (the EVKB's Arduino I2C bus) |
| 9 / 10 | LPSPI3_SCK / LPSPI3_CS | GPIO_DISP_B1_04 / GPIO_DISP_B1_03 | CS is a plain GPIO (GPIO10_IO24); QTimer TMR2, LPI2C3_SDA on B1_03 |
| 11 / 12 | LPSPI3_SOUT / LPSPI3_SIN | GPIO_DISP_B1_06 / GPIO_DISP_B1_05 | SOUT is also boot strap BOOT_CFG1[0] (100 k pull-down) |
| 13 / 14 | GPIO_LPSR_00 / GPIO_LPSR_01 | GPIO_LPSR_00 / GPIO_LPSR_01 | FLEXCAN3_TX / RX (add a transceiver), LPUART12_TXD / RXD, PDM_CLK / DATA0, MQS right / left |
| 15 / 16 | GPIO_AD_10 / GPIO_AD_11 | GPIO_AD_10 / GPIO_AD_11 | ADC1_CH2A / CH2B, FLEXPWM2_PWM0_X / PWM1_X, GPT3, FlexIO2 D10 / D11 |
| 17 / 18 | GPIO_AD_12 / GPIO_AD_13 | GPIO_AD_12 / GPIO_AD_13 | ADC1 and ADC2 CH3A / CH3B, FLEXPWM2_PWM2_X / PWM3_X, GPT1 capture, FlexIO2 D12 / D13 |
| 19 / 20 | GND / GPIO_AD_26 | — / GPIO_AD_26 | FLEXPWM2_PWM1_A, LPUART1_CTS_B, LPSPI2_SOUT, FlexIO2 D26 |

- **ADC range.** ADC_VREFH is 1.8 V, so the analog inputs read 0–1.8 V full scale. The pads
  themselves tolerate 3.3 V.
- **Why LPSPI3 and a GPIO chip select.** No complete LPSPI instance is free on 3.3 V pins that are
  not boot straps. NVCC_DISP1 is therefore 3.3 V on Nosh, and the chip select is a GPIO, because
  LPSPI3's hardware PCS0 pin (GPIO_DISP_B1_07) is boot strap BOOT_CFG1[1], encrypted XIP. A
  module's pull-up on that pin would stop the board booting.
- **Keep pull-ups off pin 11.** SOUT is BOOT_CFG1[0]; SPI slaves never drive it, so the strap reads 0.
- **SDK examples.** EVKB examples on LPI2C5 (the Arduino I2C bus) work unchanged. LPSPI examples
  written for the EVKB's Arduino SPI (LPSPI1) need the instance and pin mux changed to LPSPI3.
- If the header ends up between the board and the display, swap to a right-angle header at the
  board edge during layout.

## Differences from the MIMXRT1170-EVKB

| Block | EVKB | Nosh | Why |
|---|---|---|---|
| SDRAM | 2 × W9825G6KH-5I, 64 MB | 2 × AS4C32M16SB-6TIN, 128 MB | pin-compatible 512 Mb parts, 166 MHz; four pre-ordered at JLCPCB (C1351095, Oct 2026). W9825G6KH-6 (C62246, in stock) drops in for 64 MB |
| USB ports | two micro-AB OTG ports | micro-AB host + USB-C device | one port is enough for the host library; USB-C for programming |
| USB VBUS switch | NX5P3090UK (0.4 mm WLCSP) | TPS2553DBVR (SOT-23-6), RILIM 22 k ≈ 1.1 A | no stock, hard package; same EN/FAULT/ILIM topology |
| SD card bus | shared with the M.2 slot | separate uSDHC2 | independent Wi-Fi and SD |
| M.2 BT HCI UART | needs NXP's "HCI UART rework" (mount the shifter-output 0 R links, cut the shared Arduino / Ethernet-PHY loads, set a jumper) | hard-wired, no rework | see below |
| QSPI flash | W25Q512NWEIQ (1.8 V) | W25Q512JVEIQ (3.3 V) | NVCC_SD2 at 3.3 V keeps the SD bus simple |
| NVCC_DISP1 | 1.8 V (RGMII Ethernet PHY on GPIO_DISP_B1) | 3.3 V | no Ethernet; the bank carries the J10 SPI at 3.3 V |
| Boot configuration | DIP switch SW2 + 47 k pull-downs on the 12 BOOT_CFG pins | fixed 100 k pull-downs, no switch | always internal boot from QSPI NOR; reflash through the serial downloader (BOOT_MODE DIP) instead of changing boot devices |
| Arduino headers | four Arduino Uno R3 headers | one 2×10 expansion header J10 | the Arduino SPI pins (GPIO_AD_28..31) carry the M.2 and backlight signals here |
| LCD backlight / 2.8 V | on-board boost and LDO | none | the RK055HDMIPI4MA0 adapter (NXP SPF-39012) generates its own rails and drives its own backlight from the 5 V on FPC pins 39/40 — keep its jumpers J3/J5/J6 at the default 1-2 |
| LCD TE | 74AVC8T245 level shifter to GPIO_AD_05 | DNP 0 R | DSI video mode never uses TE; add a shifter if needed |
| Audio | WM8962 (0.5 mm WLCSP-49) with speaker outputs, electret mic and headphone jack with detect | SGTL5000 (QFN-20) with line out and line in | Teensy Audio library support; the QFN routes on standard 6-layer rules where the WLCSP needed via-in-pad; no mic, speakers or jack detect wanted |
| Not fitted at all | Ethernet (1G + 100M), CAN transceivers, camera, PMIC, LPC55 debug probe, PDM mics, accelerometer | — | use an external SWD probe; FLEXCAN3 and PDM pins are on J10 |

**No M.2 HCI UART rework.** NXP's EdgeFast Bluetooth
[hardware rework guide](https://mcuxpresso.nxp.com/mcuxsdk/25.09.00/html/middleware/edgefast_bluetooth/docs/HWRGEFBTPALUG/topics/RT1170EVKB_Murata_M2.html)
makes the EVKB + Murata M.2 combination work by mounting resistors, removing one and setting jumpers
(its designators are from an earlier EVKB build; on the RevC3 files the module-to-MCU UART_RXD/UART_CTS
links are R1901/R1902, 0 R DNP, and LPUART2's pins are shared with the Arduino header, the J57 FFC and
the Ethernet PHY reset/interrupt). Nosh needs none of it: GPIO_DISP_B2_10..13 run point-to-point through
U11/U12 (OE grounded, DIR fixed) to M.2 pins 32/22/36/34 with no 0 R links, no DNP parts and no other
loads, with the EVKB's pin mapping, so the SDK's LPUART2 flow-control setup applies unchanged. The guide's
PCM rework does not apply either: the M.2 PCM/I2S pins (8, 10, 12, 14) are not connected, so A2DP over
HCI works but HFP voice over the PCM path is not possible without a board change.

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
| SGTL5000XNLA3R2 codec | C2651833 | ~1.1 k | CS4272 (TSSOP-28, Teensy driver, line level only, 5 V analog) |
| Würth 68714014022 LCD FPC | C6264899 | ~75 | any 40-pin 0.5 mm top-contact ZIF with the same land pattern |
| CUI SJ-3523-SMT jacks | C4991872 | ~800 | — |
| TE 2199230-4 M.2 socket | C2977809 | ~5 k | — |
| AS4C32M16SB-6TIN SDRAM U9/U10 | C1351095 | 0, four pre-ordered | W9825G6KH-6 (C62246, ~8.8 k): 256 Mb, 64 MB total, SEMC COL=9 |
| YIYUAN SMTSOM2.520BTR M.2 nut H5, 2 mm | C5301776 | 0 | SMTSOM2.525BTR, 2.5 mm (C49236513, ~4.7 k): same land, the card end sits 0.5 mm higher |

Fine-pitch note: the MCU is 0.8 mm BGA; everything else is 0.4 mm QFN or coarser.

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

### Serial console J11 (0.1" 1x3)

| Pin | Signal | Connect to |
|---|---|---|
| 1 | GND | adapter GND |
| 2 | LPUART1_TXD (GPIO_AD_24), board output | adapter RX |
| 3 | LPUART1_RXD (GPIO_AD_25), board input | adapter TX |

3.3 V levels, so use a 3.3 V USB-serial adapter. LPUART1 is the SDK's default debug console,
usually 115200 8N1.

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
`in_bom = no` on the symbols), so they add nothing to the JLCPCB order. The signal test points are
1.0 mm round pads (`TestPoint_Pad_D1.0mm`, the practical minimum for a probe tip or a 1 mm pogo pin);
the six ground ones are 2.0 mm plated holes.

| Refs | Group | Nets |
|---|---|---|
| TP1–TP6 | Ground | GND; 2.0 mm plated holes, solder a wire loop for the scope ground lead |
| TP7–TP21 | Supply rails | DC_IN_F, +5V, +3V3, +1V8, VLDO_3V3, VSD_3V3, WL_3V3, SDRAM_3V3, CODEC_1V8, AUD_VDDA, LCD_5V, LCD_IOVCC_1V8, CTP_3V3, USB1_VBUS, USB2_VBUS |
| TP22–TP35 | MCU power domains | DCDC_IN, DCDC_DIG, DCDC_ANA, VDD_SOC_IN, VDDA_1P8, VDD_SNVS_IN, VDD_LPSR_IN, NVCC_LPSR, NVCC_GPIO, NVCC_SD1, NVCC_SD2, NVCC_EMC1, VDD_USB_3P3, VDDA_ADC_3P3 |
| TP36–TP49 | Reset / boot / power control | POR_B, ONOFF, WAKEUP, PMIC_ON_REQ, PMIC_STBY_REQ, BOOT_MODE0, BOOT_MODE1, DCDC_PSWITCH, DCDC_MODE, BUCK_EN, OTG2_VBUS_EN, USB_OTG2_OC, SD_PWREN_B, SD_CD_B |
| TP50–TP61 | Peripheral control (MCU side, 3.3 V) | LCM_PWR_EN, BACKLIGHT_CTL, LCD_RST_B, LCD_TE, CTP_RST_B, CTP_INT, WL_RST_B, BT_RST_B, WIFI_WAKE_B, BT_WAKE_B, WL_DEV_WAKE, BT_DEV_WAKE |
| TP62–TP72 | Buses | LPUART1_TXD / LPUART1_RXD (TP62 / TP63), LPI2C5_SDA / SCL, SAI1_MCLK, SAI1_TX_BCLK, SAI1_TX_SYNC, SAI1_TXD0, SAI1_RXD0, BT_UART_TXD / RXD |

LPUART1 (GPIO_AD_24/25, the SDK's default debug console, 3.3 V) has its own header J11 and is
also on J10 pins 5/6 and TP62/TP63. Nothing is probed on the SDRAM, FlexSPI, USB data,
MIPI DSI or crystal nets, where a pad stub would degrade the signal; SWD/SWO are on J1.

### SDRAM configuration: 10 column address bits, not 9

The EVKB's W9825G6KH (256 Mb, 16M × 16) has 13 row × 9 column bits per bank. Nosh's AS4C32M16SB
(512 Mb, 32M × 16) has 13 row × **10** column bits per bank, the same 4 banks and the same A0–A12
pins (A12 on pin 36). The hardware is identical; only the SEMC setup differs. Every EVKB-derived
SDRAM init must change in two places, or the upper half of each chip is unreachable and addresses
alias:

| Setting | EVKB (2 × 256 Mb, 64 MB) | Nosh (2 × 512 Mb, 128 MB) |
|---|---|---|
| Column address bits | 9 | 10 |
| `SEMC_SDRAMCR0[COL]` (bits 9:8) | `11b` | `10b` |
| SDK `semc_sdram_config_t.columnAddrBitNum` | `kSEMC_SdramColunm_9bit` | `kSEMC_SdramColunm_10bit` |
| Memory on chip select 0 (32-bit array = 2 chips) | 64 MB | 128 MB |
| `SEMC_BR0[MS]` (memory size) | `0_1110b`, BR0 = `0x8000001D` | `0_1111b`, BR0 = `0x8000001F` |
| SDK `memsize_kbytes` | 64 × 1024 | 128 × 1024 |
| SDRAM region | 0x8000_0000–0x83FF_FFFF | 0x8000_0000–0x87FF_FFFF |

Row bits (13), bank bits (2), bus width (32 bit, `PS=2`), CAS latency 3 and the 166 MHz SEMC clock
stay as on the EVKB. Change it in the SDK board init (`BOARD_InitSemc`), in the DCD used for XIP boot
(the `SEMC->SDRAMCR0` and `SEMC->BR[0]` writes), and in the linker script's SDRAM region length. If
the Winbond fallback (W9825G6KH-6) is ever fitted, use the EVKB values again.

## Repository layout

```
Kicad/
  Nosh.kicad_pro / Nosh.kicad_sch        project and root sheet (A3, one block per sub-sheet)
  Nosh.kicad_dru                         JLCPCB design rules, loaded automatically (see below)
  power core gpio usb supply sdram m2 sdcard lcd audio testpoints .kicad_sch
  Nosh.kicad_sym                         project symbols (MCU, flash, SDRAM, level shifters, sockets, …)
  Nosh.pretty/                           project footprints:
    slp1616p6                            RClamp0854P — EVKB IPC-D-356 land (U20/U28)
    M2_KeyE_67pin_RA                     TE 2199230-4 — pads from the EVKB IPC-D-356 data, pegs/tabs from the TE drawing
    FPC40_0p5_Wuerth_68714014022         LCD FPC — EVKB IPC-D-356 land (= Würth recommended pattern)
    L_CommonModeChoke_Murata_DLW21       USB chokes — EVKB IPC-D-356 land
    MountingHole_3.53mm_M3_Pad           M3 standoff hole, NXP spacer_139t land (EVKB IPC-D-356)
    SMTSO_M2.5_Hole4.22mm_Pad6.2mm       M.2 retention nut H5 — YIYUAN SMTSO land = EVKB BH1, 4-segment paste ring
  tools/
    gen_rt1176_symbol.py                 regenerates the MIMXRT1176DVMAA symbol from data/rt1176_{pins,mux}.json
    lcsc_table.py                        regenerates data/lcsc_parts.csv from the schematic fields
    build_board.py                       stage-1 board generator (rebuilds Nosh.kicad_pcb from the netlist; see PCB layout)
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

## PCB design rules (JLCPCB)

`Kicad/Nosh.kicad_dru` holds JLCPCB's manufacturing limits as KiCad custom DRC rules, copied
unchanged from [kicad-druid](https://github.com/Cimos/kicad-druid) (MIT licence, notice kept
in the file header; `JLCPCB/JLCPCB-6L-1oz.kicad_dru`, upstream commit `8af046d`). The 4-layer
1 oz file there has identical rules, so this file holds for either layer count. Main limits:

| Rule | Minimum |
|---|---|
| Track width / spacing | 0.09 mm / 0.09 mm |
| Via hole / annular ring | 0.15 mm / 0.05 mm; hole < 0.3 mm with diameter < 0.45 mm is flagged as extra cost |
| Via to track, PTH to track | 0.2 mm |
| Pad or via to pad or via, different nets | 0.127 mm |
| Track to board edge | 0.2 mm |

KiCad loads `<project>.kicad_dru` automatically. After editing it, open
*Board Setup → Design Rules → Custom Rules* and check for errors: a broken rule file makes KiCad
drop every rule, and `kicad-cli pcb drc` reports nothing when that happens. Update by copying a
newer upstream file over it and keeping the header.

## PCB layout

`Kicad/Nosh.kicad_pcb` is at **stage 1: floor plan**. It was generated by `Kicad/tools/build_board.py`
(KiCad's bundled Python + pcbnew), which rebuilds the board from the schematic netlist: 6 copper layers,
the JLC06161H-3313 stackup, every footprint with its nets, explicit positions for the connectors, ICs,
holes and fiducials, auto-packed passives around the part they connect to, the outline and inner GND
zones. Rerunning it discards manual board edits, so from here on edit the board in KiCad.

| Item | Value |
|---|---|
| Outline | 153.9 × 81.8 mm, square corners: the RK055 carrier's measured size (2026-10-09; `tools/shrink_outline.py` took it there from the earlier 155 × 83.5); the holes sit centred on the EVKB 147.253 × 72.905 mm pattern, which matches the carrier's holes (centres about 3 / 4 mm from the carrier edges). The carrier's FPC cable is 20.4 mm wide with its centre about 6 mm west of the carrier's centre line (user measurement 2026-10-09: 73 mm from the left carrier edge to the cable's left edge); J7 at x 70.65 is 6.3 mm west of Nosh's centre line, so the connectors line up to within the measurement error |
| Origin | north-west corner (KiCad y down). North = display connector edge = EVKB LAN edge |
| Holes H1–H4 | 147.253 × 72.905 mm pattern, centred on the outline (EVKB SS1–SS4) |
| Layers | F.Cu signal, In1 GND1, In2 SIG, In3 PWR, In4 GND2, B.Cu signal (EVKB order) |
| Stackup | JLCPCB JLC06161H-3313: 0.0994 mm prepreg to the GND layers, 0.55 mm cores, 1.6 mm, ENIG |
| Rules | min track/clearance 0.09 mm, via 0.45/0.3 mm, hole clearance 0.2 mm, edge clearance 0.3 mm (+ `Nosh.kicad_dru`) |
| Net classes | USB_90 (0.13/0.11 mm), MIPI_100 (0.11/0.13 mm), SDRAM (0.1 mm), Power (0.3 mm); the diff-pair figures are estimates for this stackup, check them with the JLCPCB impedance calculator |

Floor plan (viewed from the top): test points in three rows along the north edge; U10/U9 SDRAM west of the
MCU (SEMC balls face west); U2 flash and the M.2 level shifters east; J6 M.2 socket north-east with the card
over H5; J5 microSD, J2 micro-AB and J3 USB-C on the east edge; J8/J9 audio jacks on the south edge with
U15 above them; J10 expansion header inboard; J1 SWD and J11 UART on the south edge; J4 barrel jack on the
west edge with the supply chain beside it; SW1–SW3 in the south-west corner; SW4 boot DIP inboard north.
Bottom side: J7 display FPC at the north edge (opening north, pin 1 west as on the EVKB J48), the MCU
decoupling under the BGA, FID4–FID6.

**Stage 2 (in progress):** `tools/write_project_rules.py` rewrites the design rules and net classes
into `Nosh.kicad_pro` (KiCad overwrites that file whenever it saves the project, so close the project
before running it). The MCU has a dog-bone fan-out: 145 vias (0.45 mm pad on a 0.2 mm hole, the EVKB via; JLCPCB charges a small per-board extra for holes under 0.3 mm, but the 0.2 mm hole leaves 0.2 mm for an inner-layer track between two fan-out vias on the 0.8 mm pitch against 0.1 mm with the free 0.3 mm hole; everything else uses the free 0.45/0.3) for
every connected ball from the third ring inwards, the outer two rings escape on the top layer, and the
bottom-side decoupling sits in a ring around the via field. The PWR layer carries a +3V3 plane with
+5V (supply corner), SDRAM_3V3 (under U9/U10), WL_3V3 (M.2) and VDD_SOC_IN (MCU core) islands; GND1 and
GND2 are solid. The fan-out vias and islands are not yet joined to anything, so DRC reports them as
dangling or isolated until routing starts.

Floor-plan search (2026-10-08, `tools/floorplan/`, see its README): a simulated-annealing placer for the
macro parts scored on airwire length plus crossing airwires. Moving the SDRAM to another side of the MCU or
the M.2 slot west came out equal or worse than the EVKB-style plan, so the sides stay. A polish with the
floor plan locked moved the small blocks: U2 flash north of the MCU, J5 microSD on the north edge east of
J7, U11/U12 level shifters east, J10 header turned horizontal south-east, U15 codec beside the jacks, J1/J11
headers south-west. Macro rats-nest 5331 -> 4677 mm, crossings 1976 -> 1507, full rats-nest 4839 -> 4683 mm.

GND pours on F.Cu and B.Cu (`tools/gnd_pours.py`: 0.25 mm clearance, 0.2 mm minimum width, islands
removed, left unfilled until routing is done; a rule in `Nosh.kicad_dru` keeps any zone 0.5 mm from the
USB and MIPI pairs so the pours do not lower their impedance). Still to do: routing (the SDRAM bus,
MIPI DSI and USB pairs by hand with length matching; the rest can be autorouted and cleaned up),
reference-label tidy-up. DRC leftovers that are footprint quirks rather than layout faults: J3's NPTH-to-copper
gap is 0.19 mm against the JLC 0.2 mm rule; J2's slotted shield pads trip the JLC slot-ratio check; J2
reports a library mismatch because the Molex footprint's suggested board-edge lines were dropped on import.

**Display connector footprint fix (2026-10-06).** `Nosh.pretty/FPC40_0p5_Wuerth_68714014022` had been built
from the EVKB's bottom-side land data without mirroring, so it was a mirror image: flipped to the back in
KiCad, pin 1 would have ended up at the wrong end. It is now a normal top-side footprint (pads north of the
body, pin 1 west, cable from the south, as in Würth's land pattern); placed on the back it reproduces the
EVKB J48 arrangement, verified numerically.
