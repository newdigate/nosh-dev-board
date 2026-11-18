# Nosh bench tools

Host-side scripts for flashing and resetting a Nosh board over SWD (J1) with pyOCD and any
CMSIS-DAP probe (the bench uses an Atmel-ICE). Background: `docs/bringup-2026-11-16.md`,
sections 6d and 6r.

| Script | What it does |
|---|---|
| `nosh_flash.sh ELF [BIN]` | objcopy the FlexSPI boot image, check the FCFB (0x400) and IVT (0x1000) tags, flash it at 0x30000000, then start it with `nosh_reset.py`. `NO_RESET=1` flashes only. |
| `nosh_reset.py ELF` | Reboot without SW1: SWD SYSRESETREQ, wait for the boot ROM's warm-boot park at 0x00223104, halt there, load MSP (`_estack` from the ELF) and PC (the IVT entry), resume. |
| `srsr.py [clear]` | Read and decode SRC_SRSR (the reset-reason flags); `clear` writes 1s to clear them. The flags are sticky across resets, SW1 included. |
| `rstregs.py` | Print SRC_SCR, SRMR, SBMR2, SRSR, IOMUXC_LPSR_GPR26 (CM7 boot VTOR), the DWT PC sample, DHCSR and VTOR. |
| `hwreset.py [ms]` | Pulse the probe's nRESET (J1.10 -> D1 -> POR_B). Does not reset the board on the current bench: the Atmel-ICE never pulls the line low. |
| `pyocd_notrap.py` | pyOCD user script, used by all of the above: stops pyOCD's RT1176 target from installing its core trap code and masking reset requests (SRMR) on every connect. |

Every script attaches without halting the core. Do not halt a running Nosh image while it uses
I2C: LPI2C5 stops in debug halt and the bus wedges (section 6m). `nosh_reset.py` only halts the
core while it sits in the ROM loop.

Requirements: Python with `pyocd` importable, the Arm GNU toolchain. Overrides:

- `PYTHON`, `PYOCD`, `OBJCOPY` for `nosh_flash.sh`
- `ARM_NM` for `nosh_reset.py`

Default toolchain path is `/Applications/ARM_10/bin`. Example with a conda pyOCD:

```bash
PYTHON=/usr/local/Caskroom/miniconda/base/bin/python PYOCD=/usr/local/Caskroom/miniconda/base/bin/pyocd tools/nosh_flash.sh build/nosh_bringup.elf
```
