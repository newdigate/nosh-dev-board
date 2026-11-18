#!/bin/bash
# nosh_flash.sh ELF [BIN]: objcopy the Nosh boot image, check FCFB/IVT, flash it at 0x30000000
# with pyOCD over SWD, then start it from the host with nosh_reset.py -- no SW1 needed.
#   NO_RESET=1   flash only, leave the core parked in the ROM
#   OBJCOPY, PYOCD, PYTHON   override the tool paths (PYTHON must be able to import pyocd)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ELF=$1; BIN=${2:-${ELF%.elf}.bin}
OBJCOPY=${OBJCOPY:-/Applications/ARM_10/bin/arm-none-eabi-objcopy}
PYOCD=${PYOCD:-pyocd}
PYTHON=${PYTHON:-python3}
"$OBJCOPY" -O binary -j .text.headers -j .text.code -j .text.itcm -j .text.progmem -j .fini \
    -j .ARM.exidx -j .data -j .text.csf "$ELF" "$BIN"
ls -l "$BIN"
FCFB=$(xxd -s 0x400 -l 4 -p "$BIN"); IVT=$(xxd -s 0x1000 -l 4 -p "$BIN")
echo "FCFB@0x400: $FCFB  IVT@0x1000: $IVT"
[ "$FCFB" = "46434642" ] || { echo "no FCFB tag at 0x400 -- not a Nosh FlexSPI boot image"; exit 1; }
[ "$IVT" = "d1002041" ] || { echo "no IVT header at 0x1000 -- not a Nosh FlexSPI boot image"; exit 1; }
"$PYOCD" flash -t mimxrt1170_cm7 -O user_script="$HERE/pyocd_notrap.py" -a 0x30000000 -e sector "$BIN" 2>&1 \
    | grep -v "^ *[0-9]*ms\|WARNING" | tail -4
if [ -z "$NO_RESET" ]; then
    "$PYTHON" "$HERE/nosh_reset.py" "$ELF" 2>&1 | grep -v -E "WARNING|^Error during" | tail -2
fi
