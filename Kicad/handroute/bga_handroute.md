# MCU (U1) BGA connections to hand-route

Generated 2026-10-11 from the KiCad DRC of commit d939760: **70 open connections** have one end at the U1 ball grid (26 power, 44 signal).

Numbers match the labels in `bga_open.png` (label = the ball end; yellow = signal, cyan = power; the short bar points toward the other end).
Balls are 0.8 mm pitch, A1 at (65.6, 35.6), rows A–U top to bottom, columns 1–17 left to right. Coordinates are mm from the board origin (top-left, y down).

- **Fan-out via** is the dog-bone via already on that ball: start there. "none" means the ball has no fan-out yet (mostly the outer two rings, which escape on F.Cu).
- **Other end** is where KiCad's ratsnest line lands (a pad, or the end of copper already routed on that net) and the pads it is part of.
- Inside the grid only 0.1 mm tracks fit between the fan-out vias; no tracks on GND1, PWR or GND2.

## Inside the grid: ball-to-ball links and balls not yet on their plane (9)

| # | Net | Ball | Fan-out via | Other end | At (x, y), layer | Airline mm |
|---|---|---|---|---|---|---|
| 1 | GND ⚡ | A1 | none | plane via at (67.60, 37.60) | (67.60, 37.60) F.Cu | 2.8 |
| 2 | NVCC_EMC1 ⚡ | F7 | (70.00, 39.20) | U1 ball F6 | (69.60, 39.60) F.Cu | 0.8 |
| 3 | NVCC_EMC1 ⚡ | G6 | (69.20, 40.00) | U1 ball F6 | (69.60, 39.60) F.Cu | 0.8 |
| 4 | DCDC_ANA ⚡ | M7 | (70.00, 44.80) | U1 ball M8 | (71.20, 44.40) F.Cu | 0.8 |
| 5 | GND ⚡ | P14 | (76.40, 46.40) | U1 ball T12 | (74.40, 47.60) F.Cu | 2.3 |
| 6 | GND ⚡ | R4 | (67.60, 47.20) | U1 ball U1 | (65.60, 48.40) F.Cu | 2.3 |
| 7 | GND ⚡ | T12 | none | U1 ball T11 | (73.60, 47.60) F.Cu | 0.8 |
| 8 | DCDC_LP ⚡ | U3 | none | U1 ball T3 | (67.20, 47.60) F.Cu | 0.8 |
| 9 | DCDC_LN ⚡ | U4 | none | U1 ball T4 | (68.00, 47.60) F.Cu | 0.8 |

## Escaping south (y > 48) (30)

| # | Net | Ball | Fan-out via | Other end | At (x, y), layer | Airline mm |
|---|---|---|---|---|---|---|
| 10 | LPSPI3_SOUT | D10 | (73.20, 37.60) | J10.11, R92.1 | (82.95, 68.81) F.Cu | 32.4 |
| 11 | BT_CFG9 | D7 | (70.00, 37.60) | R101.1 | (75.49, 51.25) F.Cu | 14.2 |
| 12 | LPSPI3_SCK | E10 | (73.20, 38.40) | J10.9 | (80.41, 68.81) F.Cu | 31.0 |
| 13 | LPSPI3_CS | E11 | (74.00, 38.40) | J10.10 | (80.41, 66.27) F.Cu | 28.3 |
| 14 | VDD_MIPI_1P0 ⚡ | F10 | (73.20, 39.20) | R4.2 | (73.25, 57.26) F.Cu | 17.7 |
| 15 | GPIO_AD_13 | L12 | (74.80, 44.00) | J10.18 | (90.57, 66.27) F.Cu | 27.8 |
| 16 | LPUART1_TXD | L13 | (75.60, 44.00) | J10.5, J11.2, TP62.1 | (76.16, 59.01) F.Cu | 15.4 |
| 17 | GPIO_AD_26 | L14 | (76.40, 44.00) | J10.20 | (93.11, 66.27) F.Cu | 28.4 |
| 18 | DCDC_DIG_SENSE | L7 | (70.00, 44.00) | R8.2 | (78.00, 51.24) F.Cu | 10.8 |
| 19 | LPUART1_RXD | M15 | (77.20, 44.80) | J10.6, J11.3, TP63.1 | (76.16, 56.47) F.Cu | 12.1 |
| 20 | DCDC_IN ⚡ | M5 | (68.40, 44.80) | C23.1, C24.1 | (69.25, 52.48) F.Cu | 7.7 |
| 21 | DCDC_ANA_SENSE | M6 | (69.20, 44.80) | R7.2 | (70.25, 52.74) F.Cu | 8.4 |
| 22 | DCDC_ANA ⚡ | M7 | (70.00, 44.80) | C27.1, C28.1, C29.1, R5.1 … | (70.25, 53.76) F.Cu | 9.4 |
| 23 | GPIO_LPSR_00 | N6 | (69.20, 45.60) | J10.13 | (85.49, 68.81) F.Cu | 28.5 |
| 24 | LPI2C5_SCL | N8 | (70.80, 45.60) | J10.7, J7.27, R75.2, TP65.1 … | (84.65, 64.60) F.Cu | 23.6 |
| 25 | GPIO_AD_11 | P16 | none | J10.16 | (88.03, 66.27) F.Cu | 22.8 |
| 26 | DCDC_PSWITCH | P3 | (66.80, 46.40) | C45.1, R1.2, TP43.1 | (66.75, 53.40) B.Cu | 7.4 |
| 27 | BOOT_MODE0 | P6 | (69.20, 46.40) | R90.1 | (72.99, 51.25) F.Cu | 6.2 |
| 28 | POR_B | T10 | none | C55.1, D1.2, R9.2, SW1.1 … | (64.77, 65.21) SIG | 19.4 |
| 29 | RTC_XTALI | T13 | none | C143.1, Y2.1 | (70.96, 56.37) F.Cu | 9.7 |
| 30 | VDD_SNVS_DIG ⚡ | T14 | none | C4.1 | (75.50, 52.02) F.Cu | 4.4 |
| 31 | SWCLK | T6 | none | J1.4 | (56.65, 61.91) F.Cu | 19.3 |
| 32 | BOOT_MODE1 | T7 | none | R11.2, R91.1, TP42.1 | (67.76, 57.25) F.Cu | 10.0 |
| 33 | WAKEUP | T8 | none | C57.1, SW3.1, TP38.1 | (63.72, 59.11) F.Cu | 13.7 |
| 34 | PMIC_STBY_REQ | T9 | none | R10.1, TP40.1 | (70.26, 61.00) F.Cu | 13.5 |
| 35 | VDD_SNVS_IN ⚡ | U12 | none | C1.1, D5.1, TP27.1 | (73.73, 52.77) B.Cu | 4.4 |
| 36 | GND ⚡ | U17 | none | plane via at (78.39, 49.75) | (78.39, 49.75) F.Cu | 1.4 |
| 37 | DCDC_LP ⚡ | U3 | none | L1.1 | (61.50, 54.50) F.Cu | 8.3 |
| 38 | SWDIO | U7 | none | J1.2 | (57.92, 61.91) F.Cu | 18.4 |
| 39 | PMIC_ON_REQ | U9 | none | R28.1, TP39.1 | (50.00, 70.49) F.Cu | 31.2 |

## Escaping east (x > 79) (17)

| # | Net | Ball | Fan-out via | Other end | At (x, y), layer | Airline mm |
|---|---|---|---|---|---|---|
| 40 | M2_SDIO_D3 | A16 | none | J6.19 | (129.75, 43.77) F.Cu | 52.8 |
| 41 | BT_UART_RTS | A5 | none | U11.5 | (90.82, 41.15) F.Cu | 22.7 |
| 42 | M2_SDIO_D2 | B15 | none | J6.17 | (130.25, 43.77) F.Cu | 54.0 |
| 43 | BT_CFG1 | E12 | (74.80, 38.40) | R93.1 | (81.25, 44.74) F.Cu | 9.1 |
| 44 | SD_CMD | E14 | (76.40, 38.40) | J5.3, R53.2 | (99.95, 19.25) F.Cu | 30.9 |
| 45 | BT_CFG8 | E9 | (72.40, 38.40) | R100.1 | (83.74, 34.75) F.Cu | 12.4 |
| 46 | SD_CLK | F14 | (76.40, 39.20) | R56.1 | (88.74, 29.00) F.Cu | 16.6 |
| 47 | NVCC_SD2 ⚡ | G13 | (75.60, 40.00) | R14.1 | (85.50, 48.51) F.Cu | 13.1 |
| 48 | VDDA_ADC_3P3 ⚡ | J13 | (75.60, 42.40) | C8.1, C9.1, FB1.2, TP35.1 | (87.51, 28.68) F.Cu | 18.1 |
| 49 | SD_DAT3 | J15 | (77.20, 42.40) | J5.2, R55.1 | (98.33, 18.93) F.Cu | 31.5 |
| 50 | SAI1_TX_BCLK | K12 | (74.80, 43.20) | R82.1, TP67.1 | (91.35, 48.45) SIG | 17.9 |
| 51 | SAI1_RXD0 | K13 | (75.60, 43.20) | TP70.1, U15.16 | (97.45, 66.60) F.Cu | 32.6 |
| 52 | SAI1_TXD0 | K14 | (76.40, 43.20) | TP69.1, U15.17 | (98.25, 64.75) F.Cu | 31.3 |
| 53 | NVCC_GPIO ⚡ | M12 | (74.80, 44.80) | C37.1, C38.1, R33.2, TP30.1 | (90.50, 53.25) F.Cu | 18.4 |
| 54 | USB_OTG2_OC | N13 | (75.60, 45.60) | R24.2, TP47.1 | (83.24, 45.00) F.Cu | 8.0 |
| 55 | BT_WAKE_B | N16 | none | TP59.1, U12.18 | (98.50, 35.50) F.Cu | 23.0 |
| 56 | DCDC_MODE | N4 | (67.60, 45.60) | C46.1, R2.1, R3.2, TP44.1 | (85.45, 29.10) F.Cu | 23.7 |

## Escaping north (y < 36) (14)

| # | Net | Ball | Fan-out via | Other end | At (x, y), layer | Airline mm |
|---|---|---|---|---|---|---|
| 57 | GND ⚡ | A17 | none | plane via at (78.39, 34.25) | (78.39, 34.25) F.Cu | 1.4 |
| 58 | LCM_PWR_EN | A4 | none | R72.1, TP50.1 | (51.50, 13.75) F.Cu | 27.4 |
| 59 | NVCC_DISP1 ⚡ | D12 | (74.80, 37.60) | C39.1, R39.2 | (73.73, 34.25) F.Cu | 3.8 |
| 60 | NVCC_SD1 ⚡ | D14 | (76.40, 37.60) | C35.1, R38.2, R43.1, R44.1 … | (76.77, 34.25) F.Cu | 3.8 |
| 61 | NVCC_EMC1 ⚡ | F6 | (69.20, 39.20) | C41.1, C42.1, R34.2, TP33.1 | (69.00, 28.02) F.Cu | 11.6 |
| 62 | ADC_VREFH ⚡ | G16 | none | C14.1, R40.2 | (77.52, 32.50) B.Cu | 7.9 |
| 63 | VDD_USB_1P8 ⚡ | H12 | (74.80, 40.80) | C47.1 | (75.25, 34.23) F.Cu | 7.0 |
| 64 | FLEXSPI_A_D2 | H14 | (76.40, 40.80) | U2.3 | (74.75, 24.68) F.Cu | 16.6 |
| 65 | SD_CD_B | J16 | none | J5.10, R57.2, TP49.1 | (106.83, 6.42) F.Cu | 46.0 |
| 66 | BACKLIGHT_CTL | K17 | none | R64.1, TP51.1 | (79.25, 10.51) F.Cu | 32.3 |
| 67 | DCDC_IN ⚡ | L5 | (68.40, 44.00) | C25.1 | (60.25, 12.77) F.Cu | 32.0 |
| 68 | CTP_INT | N12 | (74.80, 45.60) | R77.1, TP55.1 | (84.50, 8.00) F.Cu | 38.5 |
| 69 | LCD_TE | P13 | (75.60, 46.40) | R67.1, TP53.1 | (77.01, 10.50) F.Cu | 35.5 |
| 70 | LCD_RST_B | R13 | (75.60, 47.20) | D9.1, TP52.1 | (67.30, 5.00) F.Cu | 42.5 |

⚡ = power net (route wider than 0.1 mm once outside the grid where there is room).
