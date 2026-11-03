# MIMXRT1170-EVKB vs Nosh: firmware porting reference

Written 2026-11-03 from the Nosh board file (`Kicad/Nosh.kicad_pcb`, commit e7e3dc3), the
EVKB RevC3 netlist (`rt1170/MIMXRT1170-EVKB-DESIGNFILES_RevC3/pst2kicad/board.net`, MCU = U19)
and the current state of `teensy-cores/imxrt1176`, `USBHost_t36`, `SPI`, `M2Radio` and
`MipiDisplay`. The per-pad table at the end was generated from the two netlists
(`rt1176_pins.json` / `rt1176_mux.json` for pad names and mux options), the rest is hand-written.

Nosh was drawn as a cut-down copy of the EVKB, so most pads keep the EVKB function. The things
that differ are: SDRAM size and speed, flash voltage, the SD card moving to uSDHC2, the M.2 socket
getting its own 1.8 V SDIO bus, the USB connectors, no Ethernet, no Arduino headers, no PMIC,
the SGTL5000 codec instead of the WM8962, and one Winbond flash command set instead of the
ISSI one the FCB comments describe.

## 1. What has to change, in one screen

| Area | EVKB (what the code assumes today) | Nosh | Firmware impact |
|---|---|---|---|
| Board select | none: `-DARDUINO_MIMXRT1170_EVKB` is passed by `teensy-cmake-macros` (TEENSY_VERSION 117) but nothing tests it | needs its own macro, e.g. `ARDUINO_NOSH` | add a board switch; today every value below is unconditional |
| SDRAM | 2 x W9825G6KH-5I (U13/U25), 256 Mb each, 32-bit, **64 MB**, 13 row x 9 col, SEMC 198 MHz | 2 x AS4C32M16SC-7TIN (U9/U10), 512 Mb each, 32-bit, **128 MB**, 13 row x 10 col, SEMC **132 MHz** | `semc.c`: clock root, COL, BR0 MS, timings, refresh; `imxrt1176.ld` ERAM 128 MB; `extmem.c`/`startup.c` size 128; `SEMC_CLOCK_HZ` |
| SEMC DQS | pad loopback, C91 10 pF on the DQS pad | same pad, C145 10 pF footprint **DNP** | keep `DQSMD(1)`; if reads are marginal fit C145 or tune DCCR |
| Boot flash | W25Q512NWEIQ (U23, **1.8 V**, 64 MB) on FlexSPI1 A; `bootdata.c` comments say IS25WP128 16 MB | W25Q512JVEIQ (U2, **3.3 V**, 64 MB), same pads, QE set at factory | same Winbond command set; FCB `sflashA1Size` 64 MB already right; linker `FLASH` 16 MB and the EEPROM 16 MB masks are conservative on both boards |
| Flash / SD2 bank | NVCC_SD2 = FLASH_VCC 1.8 V; SD_B2_00..05 go to the unpopulated octal flash U21 | NVCC_SD2 = **3.3 V**; SD_B2_00..05 = **microSD on uSDHC2** | pad voltage follows the bank: nothing to set. New: uSDHC2 instance for the card |
| microSD | uSDHC1 on GPIO_SD_B1, J15, bank switchable 3.3/1.8 V (VSELECT = GPIO_AD_34), CD = GPIO_AD_32, PWREN = GPIO_AD_35 | **uSDHC2** on GPIO_SD_B2_00..05, J5, bank fixed 3.3 V (no UHS-I), CD = GPIO_AD_34 (low = card), PWREN_B = GPIO_AD_35 (low = on, default on) | SdFat/core USDHC defines: instance 2, clock root 59, LPCG118, pads SD_B2_00..05 ALT0; CD pad moves to AD_34; no VSELECT |
| M.2 Key E (IW416 / MAYA-W1) | SDIO on uSDHC1 shared with the microSD slot, bank switched to 1.8 V by VSELECT; BT UART on LPUART2 direct 3.3 V, RTS pad doubles as the 1G PHY reset so no flow control | SDIO on **uSDHC1 alone**, NVCC_SD1 fixed **1.8 V**; BT UART on LPUART2 through 74AVC8T245 shifters with **working RTS/CTS** | M2Radio: delete the `USDHC1_VSELECT` write (`sdio/SdioHost.cpp:184`, it would drive the Nosh SD card-detect line); flow control can be enabled |
| USB device | OTG1, micro-AB, 5 V through NX5P3090 U26 (EN = GPIO_AD_10), ID on GPIO_AD_09 | OTG1, **USB-C UFP** J3 (5.1k Rd), VBUS sense only through a 300R bead, no ID | `usb.c` unchanged (it never used VBUS/ID) |
| USB host | OTG2, micro-AB J18, 5 V through NX5P3090 U18 (EN = GPIO_AD_07, pulled on), OC = GPIO_AD_06, ID = GPIO_AD_08 | OTG2, micro-AB J2, 5 V through **TPS2553** U3 switched by **hardware** (ID low -> Q2 off -> EN high), OC (FAULT) = GPIO_AD_06, ID = GPIO_AD_08 | USBHost_t36 unchanged (no GPIO on the 1176 path); `analogWrite(8)` / `digitalWrite(8)` no longer touches VBUS |
| Ethernet | RTL8201 RMII (enet.c) + RTL8211 RGMII | **none** | never call `enet_init()`; its pads are Nosh boot straps (DISP_B2_02..05), SAI-free pads and TDI (LPSR_12) |
| Audio codec | WM8962 on SAI1 + LPI2C5 (control in the Audio library) | **SGTL5000** (QFN-20, I2C 0x0A) on SAI1 + LPI2C5, RX synchronous to TX (R84/R85 DNP) | same SAI1 pads and clock; use `AudioControlSGTL5000`; MCLK must be driven (codec is slave) |
| Display | RK055HDMIPI4MA0 on J48, 2 DSI lanes, reset AD_02, backlight AD_30, power DISP_B2_15, TE AD_05 via shifter, GT911 touch on LPI2C5 (INT AD_00, RST AD_01) | identical pads on J7; **TE not connected** (R67 DNP) | MipiDisplay unchanged; do not rely on TE |
| Debug UART | LPUART1 AD_24/25 to the on-board probe (VCOM) | LPUART1 AD_24/25 on **J11 3-pin header** (GND, TX, RX) | Serial1 unchanged; external USB-UART needed |
| SWD | 20-pin JTAG J1 + on-board LPC-Link | 10-pin Cortex J1: SWDIO LPSR_15 (J1.2), SWCLK LPSR_14 (J1.4), SWO LPSR_11 (J1.6), TDI LPSR_12 (J1.8), nRESET (J1.10) -> POR_B through D1; TRST (LPSR_10) not wired | nothing in the core |
| Buttons / LEDs | SW7 user button = WAKEUP, SW6 = ONOFF, SW4 reset; user LED GPIO_AD_04 | SW3 = WAKEUP, SW2 = ONOFF, SW1 = reset (POR_B); user LED GPIO_AD_04 (high = on), power LED, two M.2 LEDs | `LED_BUILTIN` = 3 keeps working |
| Boot straps | SW1 boot mode, SW2 12-way BT_CFG DIP (47k) | SW4 2-way boot mode (100k down), BT_CFG0..11 **fixed 100k down** = FlexSPI1 NOR boot | none; serial downloader needs SW4 = 01 |
| Arduino headers | J9/J10/J25/J26, the core's 22-pin table | **none**; D0..D21 pads are internal signals or unconnected | pin table must be rewritten (section 4) |
| SPI | LPSPI1 on AD_28/30/31 to the header | those pads are BT_DEV_WAKE / BACKLIGHT_CTL / WL_RST_B; **no SPI bus wired** | `SPI` object must not claim LPSPI1 pads; see section 7 |
| Core power | PF5020 PMIC (U357) + on-chip DCDC with 0R links; DCDC_IN via jumper J19 | **on-chip DCDC only** (L1 4.7 uH), DCDC_IN = +3V3, PMIC_ON_REQ -> MP2143 buck EN, PMIC_STBY_REQ 10k down | `startup.c` DCDC VDD1P0 1.15 V now really sets VDD_SOC (it did on the EVKB too, unless the PMIC jumper option was used) |
| Rails | 5V_SYS, SENSOR_3V3, VDD_1V8 (PMIC) | +5V (TPS259531 eFuse from the jack or ORed from either USB port), +3V3 (MP2143), +1V8 (TLV1117LV-18 + DCDC_ANA 0R) | none |
| RTC / SNVS | coin cell | **no battery**: VDD_SNVS_IN from the AP2112K 3.3 V LDO via D5 | RTC loses time at power-off; `rtc.c` seed logic applies at every boot |
| ADC / DAC | VREFH jumper, DAC on TP18, A0-A5 on headers | VREFH = +1V8 via R40; DAC, CLK1 and A0-A5 pads unconnected | `analog.c` A0-A5 harmless but meaningless |

## 2. SEMC / SDRAM

Both boards use the same SEMC pad set and the same two-chip, 32-bit CS0 arrangement
(lower 16 bits on U9 = EVKB U13, upper on U10 = EVKB U25, address/control bussed to both,
CLK through 0R links R41/R42 = EVKB R365/R407). Differences are all in the configuration:

| Item | EVKB (`semc.c` today) | Nosh (AS4C32M16SC-7TIN, 2x) |
|---|---|---|
| Device | W9825G6KH-5I, 4M x 16 x 4 banks (256 Mb), 166 MHz grade | AS4C32M16SC-7TIN, 8M x 16 x 4 banks (512 Mb), 133 MHz grade |
| Total | 64 MB at 0x80000000 | **128 MB** at 0x80000000 |
| Clock root | `CCM_CLOCK_ROOT4 = MUX(6) | DIV(2)`: SYS_PLL2_PFD1 594 MHz / 3 = 198 MHz (`semc.c:151`) | `MUX(5) | DIV(3)`: SYS_PLL2 528 MHz / 4 = **132 MHz** (the reset default; SDK `kCLOCK_SEMC_ClockRoot_MuxSysPll2Out`, div 4) |
| `SEMC_CLOCK_HZ` | 198000000 (`imxrt1176.h:1758`) | 132000000 |
| BR0 | `0x80000000 | MS(14) | VLD` (64 MB) | `MS(15)` (128 MB) |
| SDRAMCR0 | PS(2) 32-bit, BL(3) burst 8, **COL(3)** 9-bit, CL(3) | PS(2), BL(3), **COL(2)** 10-bit, CL(3) |
| tRP / tRCD / tRRD | 15 / 15 / 10 ns | 15 / 15 / 15 ns (2 clk each at 132 MHz) |
| tRAS | 40 ns | 44 ns min (6 clk), 120 us max |
| tRC | - | 66 ns (9 clk) |
| tRFC (refresh recovery) | 70 ns | 66 ns (9 clk) |
| tWR | 10 ns | 15 ns (2 clk) |
| tXSR / self-refresh recovery | 70 ns | 75 ns (10 clk) |
| tMRD | - | 2 clk |
| tREF | 64 ms / 8192 rows (7.8 us) | same, 7.8 us = 1030 clk at 132 MHz (recompute the prescaler / refresh count, `semc.c:267-279`) |
| Mode register | 0x33: BL8, sequential, CL3 | same |
| DQS | `DQSMD(1)` pad loopback with C91 10 pF | `DQSMD(1)`, **no cap** (C145 DNP); fall back to internal loopback + DCCR delay if reads fail |
| Linker | `ERAM LENGTH 65536K` (`imxrt1176.ld:12`) | 131072K |
| `external_psram_size` | 64 (`startup.c:146,306`) | 128; heap in `extmem.c:65` (`64u * 0x100000u`) becomes 128 |

The MASK/DM lines, the unused SEMC_RDY/CSX0/CLKX pads and the B2_18..20 pads are not wired on
Nosh (free). SEMC D26..D31 and DM3 are direct on Nosh; on the EVKB they go through 0R links
that share pads with I2S3/PCM options. Full timing derivation is in the project README under
"SEMC clock: 132 MHz for the -7 speed grade".

## 3. Boot flash, FCB, EEPROM

- EVKB RevC3 actually carries a **W25Q512NWEIQ** (U23, 1.8 V) as the QSPI boot flash and an
  unpopulated MX25UM51345G octal footprint (U21). `bootdata.c:66-90` still describes the older
  IS25WP128 and says the FCB bytes came from the Zephyr EVKB image; it works because the
  Winbond quad read / program / erase opcodes it lists (0xEB, 0x02/0x32, 0x20, 0x60, 0x05, 0x06, 0x9F)
  are also valid on W25Q512. Nosh uses the 3.3 V twin **W25Q512JVEIQ**, so the same FCB boots Nosh.
- `sflashA1Size 0x04000000` (64 MB, `bootdata.c:119`) is right for both W25Q512 parts.
- Both parts need 4-byte addressing above 16 MB. The FCB's 3-byte 0xEB read, the linker's
  `FLASH LENGTH 16384K` (`imxrt1176.ld:11`) and `eeprom.c`'s 0x00FFFFFF masks all confine the
  image to the first 16 MB, which is safe. Using the upper 48 MB needs 0xEC/0x12/0x21/0xDC
  (4-byte) commands or ENTER 4-BYTE MODE (0xB7).
- EEPROM emulation region 0x30FC0000 (top of the first 16 MB) and `E2END` stay valid.
- Pad voltage: the FlexSPI pads sit in the SD2 bank, 1.8 V on the EVKB and 3.3 V on Nosh. The
  ROM configures the pads; nothing in the FCB names the voltage. Winbond "IQ" parts ship with
  QE = 1, so the quad pads IO2/IO3 (WP/HOLD) need no status-register write (no pull-ups fitted on
  either board).

## 4. GPIO: the Arduino pin table

`digital.c:58-92` maps D0..D21 to EVKB header pads. On Nosh those pads are:

| Pin | Pad | EVKB | Nosh signal | Keep as pin? |
|---|---|---|---|---|
| 0 | GPIO_DISP_B2_11 | D0 / Serial2 RX | BT_UART_RXD (LPUART2 RX from the M.2, via U12) | no: owned by Serial2 |
| 1 | GPIO_DISP_B2_10 | D1 / Serial2 TX | BT_UART_TXD | no: Serial2 |
| 2 | GPIO_DISP_B2_12 | D2 | BT_UART_CTS (LPUART2_CTS_B ALT3) | no: Serial2 flow control |
| 3 | GPIO_AD_04 | D3, LED_BUILTIN, PWM | USER_LED (D10 via 1k, high = on) | **yes**, LED_BUILTIN |
| 4 | GPIO_AD_06 | D4, PWM | USB_OTG2_OC (TPS2553 FAULT, input) | input only: host over-current |
| 5 | GPIO_AD_05 | D5, PWM | LCD_TE (R67 DNP: floating pad) | spare (not wired) |
| 6 | GPIO_AD_00 | D6 | CTP_INT (touch interrupt, input) | no |
| 7 | GPIO_AD_14 | D7, PWM | **unconnected** | spare pad, no connector |
| 8 | GPIO_AD_07 | D8, PWM | WL_DEV_WAKE (output to M.2) | no |
| 9 | GPIO_AD_01 | D9, PWM | CTP_RST_B (touch reset) | no |
| 10 | GPIO_AD_29 | D10 / SPI CS | WIFI_WAKE_B (input from M.2) | no |
| 11 | GPIO_AD_30 | D11 / SPI MOSI | BACKLIGHT_CTL (panel backlight enable) | no |
| 12 | GPIO_AD_31 | D12 / SPI MISO | WL_RST_B (M.2 W_DISABLE1) | no |
| 13 | GPIO_AD_28 | D13 / SPI SCK | BT_DEV_WAKE (output to M.2) | no |
| 14 | GPIO_LPSR_04 | D14 / Wire2 SDA | LPI2C5_SDA (codec + touch) | no: Wire2 |
| 15 | GPIO_LPSR_05 | D15 / Wire2 SCL | LPI2C5_SCL | no: Wire2 |
| 16-19 | GPIO_AD_10..13 | A0-A3 | **unconnected** | spare pads, no connector |
| 20 | GPIO_AD_09 | A4 / Wire SDA | **unconnected** | spare |
| 21 | GPIO_AD_08 | A5 / Wire SCL | USB_OTG2_ID (input; mux ALT0 = USB_OTG2_ID if wanted) | no |

Suggested Nosh pin table: keep the numbering where it still makes sense (3 = LED), and give the
board-level signals named constants instead of Arduino numbers (`NOSH_USER_LED`, `NOSH_SD_CD`,
`NOSH_SD_PWR_EN`, `NOSH_LCD_RST`, `NOSH_LCD_BL`, `NOSH_LCD_PWR`, `NOSH_CTP_INT`, `NOSH_CTP_RST`,
`NOSH_WL_RST`, `NOSH_BT_RST`, `NOSH_SDIO_RST`, `NOSH_WL_DEV_WAKE`, `NOSH_BT_DEV_WAKE`,
`NOSH_BT_WAKE`, `NOSH_WIFI_WAKE`, `NOSH_USB2_OC`, `NOSH_USB2_ID`, `NOSH_WAKEUP_BTN`). GPIO ports used:
GPIO9 (AD bank, ALT10) or GPIO3 (ALT5), GPIO10/GPIO4 for AD_32..35 and SD banks, GPIO11/GPIO5 for
DISP_B2, GPIO12/GPIO6 for LPSR; `interrupt_attach.c:24` lists only GPIO2/3/5/6 today.

PWM: `pwm.c:46-54` covers AD_01/04/05/06/07/14. Only AD_04 (LED) and AD_14 (free) are usable on
Nosh; the backlight pad GPIO_AD_30 has **no FlexPWM alternate** (ALT0 LPSPI1_SOUT, 4 LPUART3_TXD,
5/10 GPIO), so backlight dimming needs a GPT/TMR timer toggling the GPIO or the panel's own PWM
over DSI.

Nosh GPIO summary (bank, GPIO port/bit at ALT10 unless noted):

| Signal | Pad | GPIO | Dir | Notes |
|---|---|---|---|---|
| USER_LED | GPIO_AD_04 | GPIO9_IO03 | out | high = on (SDK BOARD_USER_LED) |
| SD_CD_B | GPIO_AD_34 | GPIO10_IO01 (ALT5 GPIO4_IO01) | in | low = card present, 10k pull-up |
| SD_PWREN_B | GPIO_AD_35 | GPIO10_IO02 | out | low = card powered; 10k pull-up so power is on at reset |
| LCD_RST_B | GPIO_AD_02 | GPIO9_IO01 | out | drive low to reset; release by output-high or input (diode to 1.8 V pull-up) |
| LCM_PWR_EN | GPIO_DISP_B2_15 | GPIO11_IO16 | out | 10k pull-up: panel powered at reset |
| BACKLIGHT_CTL | GPIO_AD_30 | GPIO9_IO29 | out | |
| LCD_TE | GPIO_AD_05 | GPIO9_IO04 | in | not connected (R67 DNP) |
| CTP_INT / CTP_RST_B | GPIO_AD_00 / GPIO_AD_01 | GPIO8_IO31 (ALT5 GPIO2_IO31) / GPIO9_IO00 (ALT5 GPIO3_IO00) | in / out | GT911 at 0x5D or 0x14 on LPI2C5 |
| WIFI_RST_B (SDIO_RESET#) | GPIO_AD_16 | GPIO9_IO15 | out | via U11 to J6.23 |
| WL_RST_B (W_DISABLE1#) | GPIO_AD_31 | GPIO9_IO30 | out | 27R + 10k pull-up to WL_3V3 |
| BT_RST_B (W_DISABLE2#) | GPIO_AD_15 | GPIO9_IO14 | out | 27R + 10k pull-up |
| WL_DEV_WAKE | GPIO_AD_07 | GPIO9_IO06 | out | via U11 to J6.66 |
| BT_DEV_WAKE | GPIO_AD_28 | GPIO9_IO27 | out | via U11 to J6.42 |
| BT_WAKE_B (UART_WAKE#) | GPIO_AD_27 | GPIO9_IO26 | in | via U12 from J6.20 |
| WIFI_WAKE_B (SDIO_WAKE#) | GPIO_AD_29 | GPIO9_IO28 | in | via U12 from J6.21 |
| USB_OTG2_OC | GPIO_AD_06 | GPIO9_IO05 | in | TPS2553 FAULT, open drain, 100k pull-up; deglitched 7.5 ms |
| USB_OTG2_ID | GPIO_AD_08 | GPIO9_IO07 or ALT0 USB_OTG2_ID | in | low = A-plug (host); hardware already switches VBUS on it |
| WAKEUP | WAKEUP pad (SNVS) | - | in | SW3 to GND |
| ONOFF | ONOFF pad | - | in | SW2 to GND (SNVS power button) |

## 5. Serial ports, I2C, audio, display

- **Serial1 = LPUART1** on GPIO_AD_24/25 (`HardwareSerial1.cpp`): unchanged, now on header J11
  (1 GND, 2 TX, 3 RX). It is still the SDK debug console.
- **Serial2 = LPUART2** on GPIO_DISP_B2_10/11 with RTS on DISP_B2_13 (ALT3): unchanged pads.
  On Nosh the RTS/CTS pads really reach the module (CTS = DISP_B2_12 ALT3), so hardware flow
  control for the IW416 HCI link becomes possible; M2Radio's comments about "no flow control on
  this board" describe the EVKB only. The lines pass through fixed-direction 74AVC8T245 shifters
  (U11 MCU -> module, U12 module -> MCU), 3.3 V on the MCU side, 1.8 V on the M.2 side.
- **LPI2C5** on GPIO_LPSR_04/05 (Wire2 in the core, `pins_arduino.h:119-124`): SGTL5000 at 0x0A
  and GT911 touch at 0x5D/0x14, 2.2k pull-ups to +3V3. **LPI2C1** (Wire, AD_08/09) has no bus on
  Nosh: AD_09 is unconnected and AD_08 is the USB ID input.
- **SAI1** (`I2S_instances.cpp`): same pads (MCLK AD_17, TX_BCLK AD_22, TX_SYNC AD_23, TXD0 AD_21,
  RXD0 AD_20). RX_BCLK/RX_SYNC (AD_19/AD_18) are not connected on Nosh (R84/R85 DNP): the codec's
  ADC output is clocked by the TX BCLK/LRCLK, so SAI1 RX must run in **synchronous-with-TX** mode
  (the core's I2S RX path should be checked for that). Audio PLL / MCLK = 512 fs as today; the
  SGTL5000 accepts 8-27 MHz SYS_MCLK and the Teensy Audio defaults (CHIP_ANA_POWER 0x4060 with
  VDDD external 1.8 V, CHIP_LINREG_CTRL 0x006C) match the Nosh supplies. Line-in J9 and
  line-out J8 only; no headphone amp or mic.
- **MIPI DSI**: two lanes + clock on the same balls, J7 pinout = EVKB J48. Control pads identical
  to the EVKB and to `MipiDisplay` (reset GPIO9_IO01, backlight GPIO9_IO29, power GPIO11_IO16).
  The 1.8 V panel reset is driven open-drain style through D9 (as the EVKB D32). TE is not wired.

## 6. USB

- **Device**: USB_OTG1 + USBPHY1 (`usb.c`) on J3, a USB-C receptacle wired as a UFP (5.1k CC
  pull-downs). VBUS reaches the USB1_VBUS ball through a 300R bead for session detection only;
  the board can be powered from it (D3 ORing diode into +5V). Nothing to change in `usb.c`.
- **Host**: USB_OTG2 + USBPHY2 (`USBHost_t36`, `utility/imxrt_usbhs.h`) on J2 micro-AB. VBUS is
  switched by the TPS2553 (U3) whose EN is driven by the ID pin through Q2: A-plug (ID low) -> VBUS
  on; B-plug or empty -> off. 1.1 A nominal limit, FAULT on GPIO_AD_06 (active low, open drain).
  The library sets `PORTSC_PP` and drives no GPIO on the 1176, so it works as is. The EVKB
  equivalent (NX5P3090 U18 enabled by GPIO_AD_07, pulled on by R152) is gone, so pin 8 /
  PWM1 SM1X no longer has a side effect on host power.
- Both PHYs run from the 24 MHz crystal (Y1), same as the EVKB.

## 7. SPI

The `SPI` library's single RT1176 instance (`SPIIMXRT1176.cpp:169-181`) muxes LPSPI1 onto
GPIO_AD_28 (SCK), AD_30 (SOUT), AD_31 (SIN) at ALT0. On Nosh those pads are BT_DEV_WAKE, the panel
backlight enable and the Wi-Fi W_DISABLE line: calling `SPI.begin()` would reset the Wi-Fi module
and toggle the backlight. No LPSPI bus is wired to any Nosh connector. Options: (a) compile the
`SPI` object out for the Nosh board; (b) point it at free pads for bench use, e.g. LPSPI3 on
GPIO_DISP_B1_04 (SCK, ALT9) / B1_05 (SIN) / B1_06 (SOUT) / B1_07 (PCS0) - but B1_06/B1_07 carry the
BT_CFG0/1 100k straps, harmless after boot - or LPSPI4 on GPIO_DISP_B2_12..14 which are the BT UART
flow-control pads. There are no test points on any of these.

## 8. Ethernet, PMIC, other EVKB-only code

- `enet.c` must never run on Nosh. Its pads: AD_32/33 (free on Nosh), DISP_B2_02..05 (BT_CFG8..11
  straps), DISP_B2_06..09 (free), LPSR_12 as PHY reset (= TDI on J1). SYS_PLL1 bring-up and
  CLOCK_ROOT51 in `enet.c:92-219` are also unneeded.
- No PMIC: LPI2C6 pads (LPSR_06/07) are free. PMIC_ON_REQ enables the MP2143 3.3 V buck
  (10k series), PMIC_STBY_REQ is tied low through 10k. `startup.c` does not talk to a PMIC, so
  nothing changes, but any future SNVS low-power work must know that PMIC_ON_REQ low **removes
  +3V3** (and with it the DCDC input).
- DCDC: `startup.c:248-266` sets VDD1P0 to 1.15 V (TRG 22) for 996 MHz overdrive. Nosh runs the
  on-chip DCDC from +3V3 with L1 4.7 uH and DCDC_MODE pulled low (R2; R3 to +3V3 DNP), DCDC_ANA
  1.8 V output feeding the +1V8 rail through R5 (together with the TLV1117LV-18 U8).
- CM4 image bank, Multicore, Cm4Slots: TCM-based, no SDRAM dependency, unchanged.
- `IntervalTimer.cpp:14-22` and `enet.c:87` assume the BUS root rate; same on both boards.
- RTC: no backup battery on Nosh.

## 9. Nosh pads with no connection (available for bench wiring)

GPIO_AD_03, AD_09, AD_10, AD_11, AD_12, AD_13, AD_14, AD_26, AD_32, AD_33; GPIO_DISP_B1_00..05;
GPIO_DISP_B2_06..09, B2_14; GPIO_EMC_B1_40, B1_41, B2_18, B2_19, B2_20; GPIO_LPSR_00, 01, 06, 07,
08, 09, 10; GPIO_SNVS_00..09; DAC_OUT, CLK1_P/N, MIPI CSI. None of them reach a header, so they
are only useful with a probe on the BGA escape vias. GPIO_AD_05 (LCD_TE) ends at the DNP R67 pad.

## 10. Per-repo checklist

**teensy-cores/imxrt1176**
- Add a board macro and gate the EVKB tables with it (`core_pins.h`, `pins_arduino.h`,
  `digital.c:58-92`, `analog.c:17-24`, `pwm.c:46-54`, `interrupt_attach.c:24`).
- `semc.c`: 132 MHz root (MUX 5 / DIV 3), COL(2), MS(15), the -7 timings and refresh counts above,
  comment fix (delay chain). `imxrt1176.h:1758` SEMC_CLOCK_HZ; `imxrt1176.ld:12` ERAM 131072K;
  `startup.c:146,306` and `extmem.c:65` 128 MB.
- `imxrt1176.h:659-674` USDHC1 microSD defines -> USDHC2 (base 0x40424000, IRQ_USDHC2, LPCG118,
  CLOCK_ROOT59) on GPIO_SD_B2_00..05 ALT0; CD GPIO_AD_34; power GPIO_AD_35 active low.
- `pins_arduino.h`: LED_BUILTIN stays 3; drop Wire (LPI2C1) pins; `PIN_SERIAL_RX/TX` 0/1 are
  Serial2's pads on both boards (pre-existing inconsistency).
- `bootdata.c`: comments only (W25Q512, 64 MB); FCB bytes work.
- `enet.c`: exclude from the Nosh build or guard `enet_init()`.
- `I2S.cpp`: RX synchronous to TX (no RX_BCLK/RX_SYNC pads).
- `startup.c:420-422` BUS 240 MHz justification (MIPI bandwidth) still applies.

**USBHost_t36**
- No code change: OTG2 host, PHY2 PLL from 24 MHz, VBUS by hardware. Update README/docs that
  describe the EVKB connector (J18 + OTG adapter): on Nosh J2 is a micro-AB with the ID switch.
- Optional: read `USBHS_PORTSC_OCC` or GPIO_AD_06 for over-current reporting.
- DMA placement rules (OCRAM `DMAMEM`, address thresholds 0x20200000/0x20240000, SDRAM at
  0x80000000) hold; the SDRAM is simply larger.

**SPI**
- `SPIIMXRT1176.cpp:169-181`: LPSPI1 pin table is wrong for Nosh (see section 7). Guard the
  `SPI` instance by board or move it to free pads. 24 MHz LPSPI root (CLOCK_ROOT43) assumption
  is board-independent.

**M2Radio**
- `sdio/SdioHost.cpp:180-191`: remove the GPIO_AD_34 ALT4 (USDHC1_VSELECT) write for Nosh; NVCC_SD1
  is hard-wired to 1.8 V and GPIO_AD_34 is the microSD card-detect input.
- SDIO_RST (GPIO_AD_16), WL_RST (GPIO_AD_31), uSDHC1 pads and LPUART2 HCI are unchanged.
  RTS/CTS flow control is now available. The M.2 USB, PCM and I2C pins are not connected on Nosh.

**MipiDisplay**
- Panel control pads identical; no change. TE is not wired on Nosh.

## 11. Per-pad table (generated)

Legend: EVKB column = EVKB net name, then what it reaches on the RevC3 board; Nosh column = Nosh
net name and what it reaches; **nc** = no connection on Nosh. "Core / library today" is the
EVKB-based code that touches the pad. Power and ground balls are omitted; the bank rails are in
the group headings.


#### GPIO_AD bank (NVCC_GPIO: 3.3 V on both boards)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| N12 | `GPIO_AD_00` | GPIO_AD_00 - Arduino D6 (J9.14/J25.15); CTP_INT option | `CTP_INT` - touch INT, J7.29 | D6 | none |
| R14 | `GPIO_AD_01` | GPIO_AD_01 - Arduino D9 (J10.4/J25.13); CTP_RST_B option | `CTP_RST_B` - touch reset, J7.28 | D9; PWM1 SM0B | none |
| R13 | `GPIO_AD_02` | GPIO_AD_02 - LCD_RST_B via D32 (SDK panel reset); J25.11 | `LCD_RST_B` - panel reset: D9 cathode, 10k to +1V8 on J7.21 (open-drain style) | MipiDisplay panel reset (GPIO9_IO01) | none |
| P15 | `GPIO_AD_03` | GPIO_AD_03 - J25.9; BACKLIGHT_CTL option (R1810) | **nc** (free) |  | free on Nosh |
| M13 | `GPIO_AD_04` | GPIO_AD_04 - USER LED (USER_LED_CTL1); Arduino D3 | `USER_LED` - red D10 via 1k (high = on) | D3 = LED_BUILTIN; PWM1 SM2A | none |
| P13 | `GPIO_AD_05` | GPIO_AD_05 - LCD TE via U355; Arduino D5 | `LCD_TE` - panel TE via R67 (DNP, 1.8 V logic) | D5; PWM1 SM2B | same pad; R67 DNP so TE is not connected |
| N13 | `GPIO_AD_06` | GPIO_AD_06 - USB_OTG2_OC (R1999); Arduino D4; AUD_INT | `USB_OTG2_OC` - U3 TPS2553 FAULT (open drain, 100k PU) | D4; PWM1 SM0X | none |
| T17 | `GPIO_AD_07` | GPIO_AD_07 - USB_OTG2_PWR -> U18 EN (R160); WL_DEV_WAKE; Arduino D8 | `WL_DEV_WAKE` - -> U11 -> J6.66 (1.8 V) | D8; PWM1 SM1X | same WL_DEV_WAKE; EVKB USB_OTG2_PWR role gone |
| R15 | `GPIO_AD_08` | GPIO_AD_08 - USB_OTG2_ID (R1814, J18.4); Arduino A5 / Wire SCL | `USB_OTG2_ID` - J2.4 ID; also gates Q2 -> U3 EN (hardware VBUS switch) | A5; Wire SCL (LPI2C1) | none |
| R16 | `GPIO_AD_09` | GPIO_AD_09 - Arduino A4 / Wire SDA; LCD_RST_B_OPT | **nc** (free) | A4; Wire SDA (LPI2C1) | free on Nosh - core must not drive it (A4) |
| R17 | `GPIO_AD_10` | GPIO_AD_10 - USB_OTG1_PWR -> U26 EN; Arduino A0 | **nc** (free) | A0 (ADC1 ch2A) | free on Nosh - core must not drive it (A0 (ADC1 ch2A)) |
| P16 | `GPIO_AD_11` | GPIO_AD_11 - Arduino A1 | **nc** (free) | A1 | free on Nosh - core must not drive it (A1) |
| P17 | `GPIO_AD_12` | GPIO_AD_12 - Arduino A2; ENET_INT_B | **nc** (free) | A2 | free on Nosh - core must not drive it (A2) |
| L12 | `GPIO_AD_13` | GPIO_AD_13 - Arduino A3 | **nc** (free) | A3 | free on Nosh - core must not drive it (A3) |
| N14 | `GPIO_AD_14` | GPIO_AD_14 - Arduino D7; CAN_STBY | **nc** (free) | D7; PWM3 SM0X | free on Nosh - core must not drive it (D7) |
| M14 | `GPIO_AD_15` | SPDIF_IN - SPDIF_IN; BT_RST# (R209) | `BT_RST_B` - M.2 W_DISABLE2 (J6.54) via 27R, 10k PU to WL_3V3 |  | same role (BT_RST), direct |
| N17 | `GPIO_AD_16` | SPDIF_OUT - SPDIF_OUT; WIFI_RST_B -> U354 (M.2 SDIO_RST) | `WIFI_RST_B` - -> U11 -> J6.23 SDIO_RESET (1.8 V) | M2Radio: SDIO_RST (GPIO9_IO15) | same role (SDIO_RST), via U11 |
| N15 | `GPIO_AD_17` | SAI1_MCLK -> WM8962 | `SAI1_MCLK` - R81 0R -> SGTL5000 SYS_MCLK | I2S MCLK (SAI1) | none |
| M16 | `GPIO_AD_18` | SAI1_RX_SYNC -> WM8962 | `SAI1_RX_SYNC` - R85 DNP (RX synchronous to TX) |  | none |
| L16 | `GPIO_AD_19` | SAI1_RX_BCLK -> WM8962 | `SAI1_RX_BCLK` - R84 DNP |  | none |
| K13 | `GPIO_AD_20` | SAI1_RXD0 <- WM8962 | `SAI1_RXD0` - <- SGTL5000 I2S_DOUT | I2S RX_DATA0 | none |
| K14 | `GPIO_AD_21` | SAI1_TXD0 -> WM8962 | `SAI1_TXD0` - -> SGTL5000 I2S_DIN | I2S TX_DATA0 | none |
| K12 | `GPIO_AD_22` | SAI1_TX_BCLK | `SAI1_TX_BCLK` - R82 0R -> I2S_SCLK | I2S TX_BCLK | none |
| J12 | `GPIO_AD_23` | SAI1_TX_SYNC | `SAI1_TX_SYNC` - R83 0R -> I2S_LRCLK | I2S TX_SYNC | none |
| L13 | `GPIO_AD_24` | LPUART1_TXD - LPUART1_TXD -> J115 -> debug probe VCOM | `LPUART1_TXD` - J11.2 debug header | Serial1 TX (LPUART1 ALT0) | none |
| M15 | `GPIO_AD_25` | LPUART1_RXD - LPUART1_RXD <- J114 | `LPUART1_RXD` - J11.3 | Serial1 RX | none |
| L14 | `GPIO_AD_26` | CSI_PWR_CTL - CSI_PWR_CTL; USER_LED_CTL2 | **nc** (free) |  | free on Nosh |
| N16 | `GPIO_AD_27` | BT_WAKE_B (M.2 UART_WAKE via R238/R811) | `BT_WAKE_B` - <- U12 <- J6.20 UART_WAKE (1.8 V) |  | same role (UART_WAKE), via U12 |
| L17 | `GPIO_AD_28` | GPIO_AD_28 - BT_DEV_WAKE -> U354; Arduino D13 / SPI SCK | `BT_DEV_WAKE` - -> U11 -> J6.42 | D13; SPI SCK (LPSPI1_SCK) | repurposed: BT_DEV_WAKE - update D13 / SPI SCK |
| M17 | `GPIO_AD_29` | GPIO_AD_29 - Arduino D10; WIFI_WAKE_B option | `WIFI_WAKE_B` - <- U12 <- J6.21 SDIO_WAKE | D10 (SPI CS by convention) | repurposed: WIFI_WAKE_B input - update D10 |
| K17 | `GPIO_AD_30` | GPIO_AD_30 - Arduino D11 / SPI MOSI; FLASH_RST option | `BACKLIGHT_CTL` - J7.34 (GPIO only on this pad: no FlexPWM alt) | D11; SPI MOSI (LPSPI1_SOUT ALT0); MipiDisplay backlight (GPIO9_IO29) | repurposed: backlight GPIO - update D11 / SPI MOSI |
| J17 | `GPIO_AD_31` | GPIO_AD_31 - WL_RST# (R404 hand-bridged); Arduino D12 / SPI MISO | `WL_RST_B` - M.2 W_DISABLE1 (J6.56) via 27R, 10k PU | D12; SPI MISO; M2Radio WL_RST (GPIO9_IO30) | same WL_RST role; D12 / SPI MISO must go |
| K16 | `GPIO_AD_32` | ENET_MDC - ENET_MDC (RTL8201 100M PHY); SD1_CD_B (R1926) | **nc** (free) | enet.c MDC | free on Nosh - core must not drive it (enet.c MDC) |
| H17 | `GPIO_AD_33` | ENET_MDIO - ENET_MDIO | **nc** (free) | enet.c MDIO | free on Nosh - core must not drive it (enet.c MDIO) |
| J16 | `GPIO_AD_34` | 1588_EVENT0_IN - 1588_EVENT0_IN; SD1_VSELECT -> U311 (R168) | `SD_CD_B` - microSD J5.10 switch, 10k PU, low = card | M2Radio SdioHost: USDHC1_VSELECT (ALT4) | repurposed: SD card detect - remove the VSELECT write in M2Radio SdioHost |
| G17 | `GPIO_AD_35` | 1588_EVENT0_OUT - 1588_EVENT0_OUT; SD_PWREN_B (R151) | `SD_PWREN_B` - 1k -> Q3 P-FET gate: low = VSD_3V3 on (10k PU: on by default) |  | same function (SD power), active low, now uSDHC2 card |

#### GPIO_DISP_B1 bank (NVCC_DISP1: EVKB 1.8 V, Nosh 3.3 V)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| E13 | `GPIO_DISP_B1_00` | ENET_RGMII_RX_EN - RGMII RX_EN (RTL8211 1G PHY) | **nc** (free) |  | free on Nosh |
| D13 | `GPIO_DISP_B1_01` | ENET_RGMII_RXC - RGMII RXC | **nc** (free) |  | free on Nosh |
| D11 | `GPIO_DISP_B1_02` | ENET_RGMII_RXD0 - RGMII RXD0 | **nc** (free) |  | free on Nosh |
| E11 | `GPIO_DISP_B1_03` | ENET_RGMII_RXD1 - RGMII RXD1 | **nc** (free) |  | free on Nosh |
| E10 | `GPIO_DISP_B1_04` | ENET_RGMII_RXD2 - RGMII RXD2 | **nc** (free) |  | free on Nosh |
| C11 | `GPIO_DISP_B1_05` | ENET_RGMII_RXD3 - RGMII RXD3 | **nc** (free) |  | free on Nosh |
| D10 | `GPIO_DISP_B1_06` | ENET_RGMII_TXD3 - RGMII TXD3; BT_CFG[0] (22k -> SW2 DIP) | `LPSPI3_SOUT` - BT_CFG0 strap, 100k to GND (misnamed net) |  | strap only (BT_CFG0 = 0); EVKB DIP replaced by 100k |
| E12 | `GPIO_DISP_B1_07` | ENET_RGMII_TXD2 - RGMII TXD2; BT_CFG[1] | `BT_CFG1` - BT_CFG1 strap, 100k to GND |  | none |
| A15 | `GPIO_DISP_B1_08` | ENET_RGMII_TXD1 - RGMII TXD1; BT_CFG[2] | `BT_CFG2` - BT_CFG2 strap, 100k to GND |  | none |
| C13 | `GPIO_DISP_B1_09` | ENET_RGMII_TXD0 - RGMII TXD0; BT_CFG[3] | `BT_CFG3` - BT_CFG3 strap, 100k to GND |  | none |
| B14 | `GPIO_DISP_B1_10` | ENET_RGMII_TX_EN - RGMII TX_EN; BT_CFG[4] | `BT_CFG4` - BT_CFG4 strap, 100k to GND |  | none |
| A14 | `GPIO_DISP_B1_11` | ENET_RGMII_TXC - RGMII TXC; BT_CFG[5] | `BT_CFG5` - BT_CFG5 strap, 100k to GND |  | none |

#### GPIO_DISP_B2 bank (NVCC_DISP2: 3.3 V both)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| E8 | `GPIO_DISP_B2_00` | GPIO_DISP_B2_00 - BT_CFG[6]; PMIC_INTB | `BT_CFG6` - BT_CFG6 strap, 100k to GND |  | none |
| F8 | `GPIO_DISP_B2_01` | GPIO_DISP_B2_01 - BT_CFG[7] | `BT_CFG7` - BT_CFG7 strap, 100k to GND |  | none |
| E9 | `GPIO_DISP_B2_02` | ENET_TXD0 - RMII TXD0 (RTL8201); BT_CFG[8]; TRACE_D0 | `BT_CFG8` - BT_CFG8 strap, 100k to GND | enet.c RMII | none |
| D7 | `GPIO_DISP_B2_03` | ENET_TXD1 - RMII TXD1; BT_CFG[9] | `BT_CFG9` - BT_CFG9 strap, 100k to GND | enet.c RMII | none |
| C7 | `GPIO_DISP_B2_04` | ENET_TXEN - RMII TXEN; BT_CFG[10] | `BT_CFG10` - BT_CFG10 strap, 100k to GND | enet.c RMII | none |
| C9 | `GPIO_DISP_B2_05` | ENET_TX_REF_CLK - RMII REF_CLK; BT_CFG[11] | `BT_CFG11` - BT_CFG11 strap, 100k to GND | enet.c RMII | none |
| C6 | `GPIO_DISP_B2_06` | ENET_RXD0 - RMII RXD0; TRACE_CLK | **nc** (free) | enet.c RMII | free on Nosh - core must not drive it (enet.c RMII) |
| D6 | `GPIO_DISP_B2_07` | ENET_RXD1 - RMII RXD1; TRACE_SWO | **nc** (free) | enet.c RMII | free on Nosh - core must not drive it (enet.c RMII) |
| B5 | `GPIO_DISP_B2_08` | ENET_CRS_DV - RMII CRS_DV | **nc** (free) | enet.c RMII | free on Nosh - core must not drive it (enet.c RMII) |
| D8 | `GPIO_DISP_B2_09` | ENET_RXER - RMII RXER | **nc** (free) | enet.c RMII | free on Nosh - core must not drive it (enet.c RMII) |
| D9 | `GPIO_DISP_B2_10` | BT_UART_TXD - BT_UART_TXD (M.2 J54, direct 3.3 V); Arduino D1; CAN3_TX option | `BT_UART_TXD` - LPUART2 TX -> U11 -> J6.22 | D1; Serial2 TX | none |
| A6 | `GPIO_DISP_B2_11` | BT_UART_RXD - BT_UART_RXD; Arduino D0; CAN3_RX option | `BT_UART_RXD` - LPUART2 RX <- U12 <- J6.32 | D0; Serial2 RX (LPUART2_RXD ALT2) | none |
| B6 | `GPIO_DISP_B2_12` | BT_UART_CTS - BT_UART_CTS; Arduino D2 | `BT_UART_CTS` - LPUART2 CTS <- U12 <- J6.36 | D2 | real LPUART2 CTS now (EVKB: D2 only) |
| A5 | `GPIO_DISP_B2_13` | BT_UART_RTS - BT_UART_RTS = ETHPHY_RST_B (R1866, 1G PHY reset) | `BT_UART_RTS` - LPUART2 RTS -> U11 -> J6.34 | Serial2 RTS (ALT3) | real LPUART2 RTS now (EVKB: PHY reset) |
| A7 | `GPIO_DISP_B2_14` | CSI_RST_B - CSI_RST_B; HP_DET_B | **nc** (free) |  | free on Nosh |
| A4 | `GPIO_DISP_B2_15` | LCM_PWR_EN - LCM_PWR_EN (panel power, R848/R1825) | `LCM_PWR_EN` - J7.32, 10k PU to +3V3 | MipiDisplay panel power (GPIO11_IO16) | none |

#### GPIO_EMC_B1 bank (NVCC_EMC1: 3.3 V both) - SEMC

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| F3 | `GPIO_EMC_B1_00` | SEMC_D0 | `SEMC_D0` | semc.c | none |
| F2 | `GPIO_EMC_B1_01` | SEMC_D1 | `SEMC_D1` | semc.c | none |
| G4 | `GPIO_EMC_B1_02` | SEMC_D2 | `SEMC_D2` | semc.c | none |
| E4 | `GPIO_EMC_B1_03` | SEMC_D3 | `SEMC_D3` | semc.c | none |
| H5 | `GPIO_EMC_B1_04` | SEMC_D4 | `SEMC_D4` | semc.c | none |
| F4 | `GPIO_EMC_B1_05` | SEMC_D5 | `SEMC_D5` | semc.c | none |
| H4 | `GPIO_EMC_B1_06` | SEMC_D6 | `SEMC_D6` | semc.c | none |
| H3 | `GPIO_EMC_B1_07` | SEMC_D7 | `SEMC_D7` | semc.c | none |
| F5 | `GPIO_EMC_B1_08` | SEMC_DM0 | `SEMC_DM0` | semc.c | none |
| A3 | `GPIO_EMC_B1_09` | SEMC_A0 | `SEMC_A0` | semc.c | none |
| A2 | `GPIO_EMC_B1_10` | SEMC_A1 | `SEMC_A1` | semc.c | none |
| C2 | `GPIO_EMC_B1_11` | SEMC_A2 | `SEMC_A2` | semc.c | none |
| C5 | `GPIO_EMC_B1_12` | SEMC_A3 | `SEMC_A3` | semc.c | none |
| D5 | `GPIO_EMC_B1_13` | SEMC_A4 | `SEMC_A4` | semc.c | none |
| B1 | `GPIO_EMC_B1_14` | SEMC_A5 | `SEMC_A5` | semc.c | none |
| C1 | `GPIO_EMC_B1_15` | SEMC_A6 | `SEMC_A6` | semc.c | none |
| D3 | `GPIO_EMC_B1_16` | SEMC_A7 | `SEMC_A7` | semc.c | none |
| B3 | `GPIO_EMC_B1_17` | SEMC_A8 | `SEMC_A8` | semc.c | none |
| B4 | `GPIO_EMC_B1_18` | SEMC_A9 | `SEMC_A9` | semc.c | none |
| C4 | `GPIO_EMC_B1_19` | SEMC_A11 | `SEMC_A11` | semc.c | none |
| C3 | `GPIO_EMC_B1_20` | SEMC_A12 | `SEMC_A12` | semc.c | none |
| G2 | `GPIO_EMC_B1_21` | SEMC_BA0 | `SEMC_BA0` | semc.c | none |
| H2 | `GPIO_EMC_B1_22` | SEMC_BA1 | `SEMC_BA1` | semc.c | none |
| B2 | `GPIO_EMC_B1_23` | SEMC_A10 | `SEMC_A10` | semc.c | none |
| J5 | `GPIO_EMC_B1_24` | SEMC_CAS | `SEMC_CAS` | semc.c | none |
| J4 | `GPIO_EMC_B1_25` | SEMC_RAS | `SEMC_RAS` | semc.c | none |
| J3 | `GPIO_EMC_B1_26` | SEMC_CLK | `SEMC_CLK` - 0R R41/R42 to U9/U10 CLK | semc.c | none |
| G5 | `GPIO_EMC_B1_27` | SEMC_CKE | `SEMC_CKE` | semc.c | none |
| E5 | `GPIO_EMC_B1_28` | SEMC_WE | `SEMC_WE` | semc.c | none |
| E6 | `GPIO_EMC_B1_29` | SEMC_CS0 | `SEMC_CS0` | semc.c | none |
| E3 | `GPIO_EMC_B1_30` | SEMC_D8 | `SEMC_D8` | semc.c | none |
| D2 | `GPIO_EMC_B1_31` | SEMC_D9 | `SEMC_D9` | semc.c | none |
| D1 | `GPIO_EMC_B1_32` | SEMC_D10 | `SEMC_D10` | semc.c | none |
| E2 | `GPIO_EMC_B1_33` | SEMC_D11 | `SEMC_D11` | semc.c | none |
| E1 | `GPIO_EMC_B1_34` | SEMC_D12 | `SEMC_D12` | semc.c | none |
| F1 | `GPIO_EMC_B1_35` | SEMC_D13 | `SEMC_D13` | semc.c | none |
| G1 | `GPIO_EMC_B1_36` | SEMC_D14 | `SEMC_D14` | semc.c | none |
| H1 | `GPIO_EMC_B1_37` | SEMC_D15 | `SEMC_D15` | semc.c | none |
| J1 | `GPIO_EMC_B1_38` | SEMC_DM1 | `SEMC_DM1` | semc.c | none |
| J2 | `GPIO_EMC_B1_39` | SEMC_DQS pad, C91 10 pF to GND | `SEMC_DQS` - pad only; C145 10 pF footprint DNP | semc.c | same pad; no 10 pF unless C145 fitted |
| K1 | `GPIO_EMC_B1_40` | SEMC_RDY - SEMC_RDY (TP, hyperRAM U14 option) | **nc** (free) |  | not used |
| L1 | `GPIO_EMC_B1_41` | SEMC_CSX0 - SEMC_CSX0 (TP, U14 option) | **nc** (free) |  | not used |

#### GPIO_EMC_B2 bank (NVCC_EMC2: 3.3 V both) - SEMC

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| K2 | `GPIO_EMC_B2_00` | SEMC_D16 | `SEMC_D16` | semc.c | none |
| K4 | `GPIO_EMC_B2_01` | SEMC_D17 | `SEMC_D17` | semc.c | none |
| K3 | `GPIO_EMC_B2_02` | SEMC_D18 | `SEMC_D18` | semc.c | none |
| R1 | `GPIO_EMC_B2_03` | SEMC_D19 | `SEMC_D19` | semc.c | none |
| M1 | `GPIO_EMC_B2_04` | SEMC_D20 | `SEMC_D20` | semc.c | none |
| N1 | `GPIO_EMC_B2_05` | SEMC_D21 | `SEMC_D21` | semc.c | none |
| T1 | `GPIO_EMC_B2_06` | SEMC_D22 | `SEMC_D22` | semc.c | none |
| M3 | `GPIO_EMC_B2_07` | SEMC_D23 | `SEMC_D23` | semc.c | none |
| P1 | `GPIO_EMC_B2_08` | SEMC_DM2 | `SEMC_DM2` | semc.c | none |
| N2 | `GPIO_EMC_B2_09` | SEMC_D24 | `SEMC_D24` | semc.c | none |
| R2 | `GPIO_EMC_B2_10` | SEMC_D25 | `SEMC_D25` | semc.c | none |
| L4 | `GPIO_EMC_B2_11` | CCM_GL_CLKO2 - SEMC_D26 via R1983; CCM_GL_CLKO2 TP | `SEMC_D26` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| M2 | `GPIO_EMC_B2_12` | CCM_LPSR_CLKO - SEMC_D27 via R1984; CCM_LPSR_CLKO TP | `SEMC_D27` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| K5 | `GPIO_EMC_B2_13` | SEMC_D28 via R1985; BT_PCM_RXD option | `SEMC_D28` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| M4 | `GPIO_EMC_B2_14` | SEMC_D29 via R1986; BT_PCM_TXD option | `SEMC_D29` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| L2 | `GPIO_EMC_B2_15` | SEMC_D30 via R1987; BT_PCM_BCLK option | `SEMC_D30` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| P2 | `GPIO_EMC_B2_16` | SEMC_D31 via R1988; BT_PCM_SYNC option | `SEMC_D31` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| T2 | `GPIO_EMC_B2_17` | SEMC_DM3 via R1989 | `SEMC_DM3` | semc.c | SEMC D26-31/DM3 now direct (no 0R link); same mux |
| N3 | `GPIO_EMC_B2_18` | TP21 (SEMC_DQS4) | **nc** (free) |  | not used |
| U2 | `GPIO_EMC_B2_19` | ENET_RGMII_MDC - RGMII MDC | **nc** (free) |  | not used |
| R3 | `GPIO_EMC_B2_20` | ENET_RGMII_MDIO - RGMII MDIO | **nc** (free) |  | not used |

#### GPIO_LPSR bank (NVCC_LPSR: 3.3 V both)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| N6 | `GPIO_LPSR_00` | CAN3_TX - CAN3_TX (J102) | **nc** (free) |  | free on Nosh |
| R6 | `GPIO_LPSR_01` | CAN3_RX - CAN3_RX (J103) | **nc** (free) |  | free on Nosh |
| P6 | `GPIO_LPSR_02` | GPIO_LPSR_02 - BOOT_MODE[0] (SW1.4, 100k down) | `BOOT_MODE0` - SW4 DIP via 4.7k, 100k down | boot strap | none |
| T7 | `GPIO_LPSR_03` | GPIO_LPSR_03 - BOOT_MODE[1] (SW1.3) | `BOOT_MODE1` - SW4 DIP via 4.7k, 100k down | boot strap | none |
| N7 | `GPIO_LPSR_04` | GPIO_LPSR_04 - LPI2C5_SDA: WM8962 (U368), LCD touch J48.26, Arduino D14 | `LPI2C5_SDA` - SGTL5000 (0x0A) + GT911 touch J7.26, 2.2k PU | D14; Wire2 SDA (LPI2C5) | none |
| N8 | `GPIO_LPSR_05` | GPIO_LPSR_05 - LPI2C5_SCL: WM8962, J48.27, Arduino D15 | `LPI2C5_SCL` - as SDA, J7.27 | D15; Wire2 SCL | none |
| P8 | `GPIO_LPSR_06` | I2C6_SDA - I2C6_SDA -> PF5020 PMIC (U357) | **nc** (free) |  | free on Nosh |
| R8 | `GPIO_LPSR_07` | I2C6_SCL - I2C6_SCL -> PMIC | **nc** (free) |  | free on Nosh |
| U8 | `GPIO_LPSR_08` | DMIC_CLK - DMIC_CLK | **nc** (free) |  | free on Nosh |
| P5 | `GPIO_LPSR_09` | DMIC_DATA0 - DMIC_DATA0 | **nc** (free) |  | free on Nosh |
| R5 | `GPIO_LPSR_10` | JTAG_NTRST - JTAG_NTRST (J1.3) | **nc** (free) | debug probe | free on Nosh - core must not drive it (debug probe) |
| T5 | `GPIO_LPSR_11` | JTAG_TDO - JTAG_TDO / SWO (J1.13) | `SWO` - J1.6 | debug probe | none |
| U5 | `GPIO_LPSR_12` | JTAG_TDI - JTAG_TDI (J1.5); enet.c uses it as PHY reset | `TDI` - J1.8 | enet.c PHY reset (GPIO12_IO12) | none |
| U6 | `GPIO_LPSR_13` | JTAG_MOD, 10k to GND | `JTAG_MOD` - 10k to GND (SWD/JTAG mode) |  | none |
| T6 | `GPIO_LPSR_14` | JTAG_TCK - JTAG_TCK / SWCLK (J1.9) | `SWCLK` - J1.4 | debug probe | none |
| U7 | `GPIO_LPSR_15` | JTAG_TMS - JTAG_TMS / SWDIO (J1.7) | `SWDIO` - J1.2 | debug probe | none |

#### GPIO_SD_B1 bank (NVCC_SD1: EVKB switchable 3.3/1.8 V, Nosh fixed 1.8 V)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| B16 | `GPIO_SD_B1_00` | uSDHC1 CMD: microSD J15.3 and M.2 J54.11 (shared bus) | `M2_SDIO_CMD` - uSDHC1 CMD -> J6.11 (1.8 V, 10k PU) | USDHC1 defines (imxrt1176.h); M2Radio SDIO | same uSDHC1 pads; M.2 only, bank fixed 1.8 V (no VSELECT), no microSD |
| D15 | `GPIO_SD_B1_01` | SD1_CLK - uSDHC1 CLK: J15.5 / J54.9 | `M2_SDIO_CLK` - uSDHC1 CLK -> J6.9 | USDHC1 defines (imxrt1176.h); M2Radio SDIO | same uSDHC1 pads; M.2 only, bank fixed 1.8 V (no VSELECT), no microSD |
| C15 | `GPIO_SD_B1_02` | uSDHC1 D0: J15.7 / J54.13 | `M2_SDIO_D0` - J6.13 (10k PU) | USDHC1 defines (imxrt1176.h); M2Radio SDIO | same uSDHC1 pads; M.2 only, bank fixed 1.8 V (no VSELECT), no microSD |
| B17 | `GPIO_SD_B1_03` | uSDHC1 D1: J15.8 / J54.15 | `M2_SDIO_D1` - J6.15 | USDHC1 defines (imxrt1176.h); M2Radio SDIO | same uSDHC1 pads; M.2 only, bank fixed 1.8 V (no VSELECT), no microSD |
| B15 | `GPIO_SD_B1_04` | uSDHC1 D2: J15.1 / J54.17 | `M2_SDIO_D2` - J6.17 | USDHC1 defines (imxrt1176.h); M2Radio SDIO | same uSDHC1 pads; M.2 only, bank fixed 1.8 V (no VSELECT), no microSD |
| A16 | `GPIO_SD_B1_05` | uSDHC1 D3: J15.2 / J54.19 | `M2_SDIO_D3` - J6.19 | USDHC1 defines (imxrt1176.h); M2Radio SDIO | same uSDHC1 pads; M.2 only, bank fixed 1.8 V (no VSELECT), no microSD |

#### GPIO_SD_B2 bank (NVCC_SD2: EVKB 1.8 V FLASH_VCC, Nosh 3.3 V)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| J15 | `GPIO_SD_B2_00` | FLEXSPI_B_D3 - FLEXSPI1_B_D3 -> octal flash U21 (option) | `SD_DAT3` - uSDHC2 D3 -> J5.2 (100k down) |  | repurposed: microSD on uSDHC2 (new driver instance) |
| J14 | `GPIO_SD_B2_01` | FLEXSPI_B_D2 - FLEXSPI1_B_D2 (U21) | `SD_DAT2` - uSDHC2 D2 -> J5.1 |  | repurposed: microSD on uSDHC2 (new driver instance) |
| H13 | `GPIO_SD_B2_02` | FLEXSPI_B_D1 - FLEXSPI1_B_D1 (U21) | `SD_DAT1` - uSDHC2 D1 -> J5.8 |  | repurposed: microSD on uSDHC2 (new driver instance) |
| E15 | `GPIO_SD_B2_03` | FLEXSPI_B_D0 - FLEXSPI1_B_D0 (U21) | `SD_DAT0` - uSDHC2 D0 -> J5.7 (10k PU) |  | repurposed: microSD on uSDHC2 (new driver instance) |
| F14 | `GPIO_SD_B2_04` | FLEXSPI_B_CLK - FLEXSPI1_B_CLK (U21) | `SD_CLK` - uSDHC2 CLK -> 0R -> J5.5 |  | repurposed: microSD on uSDHC2 (new driver instance) |
| E14 | `GPIO_SD_B2_05` | FLEXSPI1_A_DQS (U21) | `SD_CMD` - uSDHC2 CMD -> J5.3 (10k PU) |  | repurposed: microSD on uSDHC2 (new driver instance) |
| F17 | `GPIO_SD_B2_06` | FLEXSPI_A_SS0 - FLEXSPI1_A_SS0 -> W25Q512NW (U23) / U21 | `FLEXSPI_A_SS0` - W25Q512JV CS (10k PU) | boot ROM FlexSPI1 (FCB in bootdata.c) | same pads; 3.3 V W25Q512JV instead of 1.8 V W25Q512NW |
| G14 | `GPIO_SD_B2_07` | FLEXSPI_A_CLK - FLEXSPI1_A_CLK | `FLEXSPI_A_CLK` - flash CLK | boot ROM FlexSPI1 (FCB in bootdata.c) | same pads; 3.3 V W25Q512JV instead of 1.8 V W25Q512NW |
| F15 | `GPIO_SD_B2_08` | FLEXSPI_A_D0 - FLEXSPI1_A_D0 | `FLEXSPI_A_D0` - flash IO0 | boot ROM FlexSPI1 (FCB in bootdata.c) | same pads; 3.3 V W25Q512JV instead of 1.8 V W25Q512NW |
| H15 | `GPIO_SD_B2_09` | FLEXSPI_A_D1 - FLEXSPI1_A_D1 | `FLEXSPI_A_D1` - flash IO1 | boot ROM FlexSPI1 (FCB in bootdata.c) | same pads; 3.3 V W25Q512JV instead of 1.8 V W25Q512NW |
| H14 | `GPIO_SD_B2_10` | FLEXSPI_A_D2 - FLEXSPI1_A_D2 (33k PU DNP) | `FLEXSPI_A_D2` - flash IO2/WP | boot ROM FlexSPI1 (FCB in bootdata.c) | same pads; 3.3 V W25Q512JV instead of 1.8 V W25Q512NW |
| F16 | `GPIO_SD_B2_11` | FLEXSPI_A_D3 - FLEXSPI1_A_D3 (33k PU DNP) | `FLEXSPI_A_D3` - flash IO3/HOLD | boot ROM FlexSPI1 (FCB in bootdata.c) | same pads; 3.3 V W25Q512JV instead of 1.8 V W25Q512NW |

#### GPIO_SNVS bank

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| R10 | `GPIO_SNVS_00` | GPIO_SNVS_00 | **nc** (free) |  | free on Nosh |
| P10 | `GPIO_SNVS_01` | GPIO_SNVS_01 | **nc** (free) |  | free on Nosh |
| L9 | `GPIO_SNVS_02` | GPIO_SNVS_02 | **nc** (free) |  | free on Nosh |
| M10 | `GPIO_SNVS_03` | GPIO_SNVS_03 | **nc** (free) |  | free on Nosh |
| N10 | `GPIO_SNVS_04` | GPIO_SNVS_04 | **nc** (free) |  | free on Nosh |
| P9 | `GPIO_SNVS_05` | GPIO_SNVS_05 | **nc** (free) |  | free on Nosh |
| M9 | `GPIO_SNVS_06` | GPIO_SNVS_06 | **nc** (free) |  | free on Nosh |
| R9 | `GPIO_SNVS_07` | GPIO_SNVS_07 | **nc** (free) |  | free on Nosh |
| N9 | `GPIO_SNVS_08` | GPIO_SNVS_08 | **nc** (free) |  | free on Nosh |
| R11 | `GPIO_SNVS_09` | GPIO_SNVS_09 | **nc** (free) |  | free on Nosh |

#### Dedicated pads (USB, MIPI, clocks, DCDC, analog, control)

| Ball | Pad | EVKB | Nosh | Core / library today | Change |
|---|---|---|---|---|---|
| G16 | `ADC_VREFH` | VDD_VREFH - VDD_VREFH (J116 select) | `ADC_VREFH` - R40 0R from +1V8 |  | VREFH tied to +1V8 (EVKB VDD_VREFH jumper) |
| T15 | `CLK1_N` | TP22 | nc |  | not wired |
| U15 | `CLK1_P` | TP23 | nc |  | not wired |
| H16 | `DAC_OUT` | TP18 | nc |  | not wired |
| M7 | `DCDC_ANA_1` | DCDC 1.8 V out, 0R links to PMIC SW2 rail | `DCDC_ANA` - 1.8 V out -> R5 0R -> +1V8 rail |  | none |
| M8 | `DCDC_ANA_2` | as above | `DCDC_ANA` - 1.8 V out -> R5 0R -> +1V8 rail |  | none |
| M6 | `DCDC_ANA_SENSE` | DCDC_1V8_OUT sense | `DCDC_ANA_SENSE` - R7 0R to DCDC_ANA |  | none |
| K8 | `DCDC_DIG_1` | DCDC 1.0/1.1 V out, 0R links to PMIC SW1 rail | `DCDC_DIG` - VDD_SOC via NT1, TP6 |  | none |
| K9 | `DCDC_DIG_2` | as above | `DCDC_DIG` - VDD_SOC via NT1, TP6 |  | none |
| L8 | `DCDC_DIG_3` | as above | `DCDC_DIG` - VDD_SOC via NT1, TP6 |  | none |
| L7 | `DCDC_DIG_SENSE` | sense | `DCDC_DIG_SENSE` |  | none |
| M5 | `DCDC_IN_1` | MCU_DCDC_IN - MCU_DCDC_IN (J19 jumper from 3V3) | `+3V3` - +3V3 |  | none |
| N5 | `DCDC_IN_2` | MCU_DCDC_IN - MCU_DCDC_IN | `+3V3` - +3V3 |  | none |
| L5 | `DCDC_IN_Q` | MCU_DCDC_IN - MCU_DCDC_IN | `+3V3` - +3V3 |  | none |
| T4 | `DCDC_LN_1` | inductor | `DCDC_LN` - L1 4.7 uH |  | none |
| U4 | `DCDC_LN_2` | inductor | `DCDC_LN` - L1 4.7 uH |  | none |
| T3 | `DCDC_LP_1` | inductor | `DCDC_LP` - L1 4.7 uH |  | none |
| U3 | `DCDC_LP_2` | inductor | `DCDC_LP` - L1 4.7 uH |  | none |
| N4 | `DCDC_MODE` | 4.7k/4.7k divider (R397/R398) | `DCDC_MODE` - 4.7k down (R2); 4.7k to +3V3 (R3) DNP |  | none |
| P3 | `DCDC_PSWITCH` | 30k (R396), J77 | `DCDC_PSWITCH` - 30k (R1) |  | none |
| A12 | `MIPI_CSI_CKN` | MIPI_CSI_CLKN | nc |  | free on Nosh |
| B12 | `MIPI_CSI_CKP` | MIPI_CSI_CLKP | nc |  | free on Nosh |
| A11 | `MIPI_CSI_DN0` | MIPI_CSI_DN0 | nc |  | free on Nosh |
| A13 | `MIPI_CSI_DN1` | MIPI_CSI_DN1 | nc |  | free on Nosh |
| B11 | `MIPI_CSI_DP0` | MIPI_CSI_DP0 | nc |  | free on Nosh |
| B13 | `MIPI_CSI_DP1` | MIPI_CSI_DP1 | nc |  | free on Nosh |
| A9 | `MIPI_DSI_CKN` | MIPI_DSI_CLKN | `MIPI_DSI_CLKN` - J7.11 | MipiDisplay | none |
| B9 | `MIPI_DSI_CKP` | MIPI_DSI_CLKP | `MIPI_DSI_CLKP` - J7.12 | MipiDisplay | none |
| A8 | `MIPI_DSI_DN0` | MIPI_DSI_DN0 | `MIPI_DSI_D0N` - J7.5 | MipiDisplay | none |
| A10 | `MIPI_DSI_DN1` | MIPI_DSI_DN1 | `MIPI_DSI_D1N` - J7.8 | MipiDisplay | none |
| B8 | `MIPI_DSI_DP0` | MIPI_DSI_DP0 | `MIPI_DSI_D0P` - J7.6 | MipiDisplay | none |
| B10 | `MIPI_DSI_DP1` | MIPI_DSI_DP1 | `MIPI_DSI_D1P` - J7.9 | MipiDisplay | none |
| D12 | `NVCC_DISP1` | VDD_1V8 - VDD_1V8 (RGMII bank at 1.8 V) | `+3V3` - +3V3 |  | bank 1.8 V -> 3.3 V (no RGMII) |
| E7 | `NVCC_DISP2` | SENSOR_3V3 - SENSOR_3V3 | `+3V3` - +3V3 |  | none |
| P7 | `NVCC_LPSR` | SENSOR_3V3 - SENSOR_3V3 | `+3V3` - +3V3 |  | none |
| U11 | `NVCC_SNVS` | VDD_SNVS_ANA - VDD_SNVS_ANA | `VDD_SNVS_ANA` |  | none |
| U10 | `ONOFF` | ONOFF - SW6 | `ONOFF` - SW2 |  | none |
| U9 | `PMIC_ON_REQ` | PMIC_ON_REQ - to PF5020 | `PMIC_ON_REQ` - 10k -> BUCK_EN (MP2143 EN) |  | none |
| T9 | `PMIC_STBY_REQ` | PMIC_STBY_REQ - to PF5020 | `PMIC_STBY_REQ` - 10k to GND |  | none |
| T10 | `POR` | POR_PIN_RST_B - POR_PIN_RST_B: D2 from probe, 74LVC07 U361, headers | `POR_B` - TLV803S U16, SW1, D1 from J1.10, TP7 |  | none |
| T13 | `RTC_XTALI` | 32.768 kHz Y? | `RTC_XTALI` - 32.768 kHz Y2 |  | none |
| U13 | `RTC_XTALO` | - | `RTC_XTALO` |  | none |
| T11 | `TEST_MODE` | GND - GND | `GND` - GND |  | none |
| E16 | `USB1_DN` | OTG1_DN - OTG1 D- | `USB1_DN` - J3 | usb.c device (USB_OTG1) | as USB1_DP |
| E17 | `USB1_DP` | OTG1_DP - OTG1 D+ (micro-AB, device/OTG) | `USB1_DP` - J3 USB-C (UFP, 5.1k Rd) via choke | usb.c device (USB_OTG1) | same controller; USB-C UFP: no VBUS switch, no ID pin |
| D17 | `USB1_VBUS` | 5V_USB_OTG1 - 5V_USB_OTG1 via L39 (U26 NX5P3090 switch) | `USB1_VBUS` - J3 VBUS via FB8 300R (sense only) | usb.c device (USB_OTG1) | sense only (EVKB: switched 5 V) |
| C16 | `USB2_DN` | OTG2_DN - OTG2 D- | `USB2_DN` - J2 | USBHost_t36 (USB_OTG2) | as USB2_DP |
| C17 | `USB2_DP` | OTG2_DP - OTG2 D+ (micro-AB J18, host) | `USB2_DP` - J2 micro-AB host via choke | USBHost_t36 (USB_OTG2) | same controller; VBUS switch is hardware (ID -> Q2 -> U3), no GPIO |
| D16 | `USB2_VBUS` | 5V_USB_OTG2 - 5V_USB_OTG2 via L37 (U18 NX5P3090 switch, EN = GPIO_AD_07) | `USB2_VBUS` - U3 TPS2553 out -> FB7 -> J2.1; 1.1 A limit | USBHost_t36 (USB_OTG2) | TPS2553, 1.1 A; FAULT on GPIO_AD_06 |
| H8 | `VDD_SOC_IN_1` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| H9 | `VDD_SOC_IN_2` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| H10 | `VDD_SOC_IN_3` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| J8 | `VDD_SOC_IN_4` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| J9 | `VDD_SOC_IN_5` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| J10 | `VDD_SOC_IN_6` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| K10 | `VDD_SOC_IN_7` | VDD_SOC_IN | `VDD_SOC_IN` |  | none |
| T8 | `WAKEUP` | USER_BUTTON - USER_BUTTON SW7 | `WAKEUP` - SW3 |  | none |
| U16 | `XTALI` | 24 MHz Y4 | nc |  | free on Nosh |
| T16 | `XTALO` | - | nc |  | free on Nosh |

