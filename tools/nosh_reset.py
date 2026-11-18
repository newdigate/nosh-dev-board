#!/usr/bin/env python3
"""nosh_reset.py ELF -- reboot Nosh from the host, no SW1.

1. Attach without halting and without pyOCD's RT1176 trap hooks (pyocd_notrap.py).
2. Request a system reset: AIRCR = VECTKEY | SYSRESETREQ (SRMR M7REQ must be 0 = reset system).
3. The boot ROM re-reads the FCB, configures FlexSPI, then parks the M7 in a `b .` at 0x00223104
   instead of jumping to the image (warm boots only; POR_B / SW1 boots normally).  Wait for that.
4. Halt in the ROM loop (no application running, so no I2C to wedge), load MSP = _estack from the
   ELF and PC = the IVT entry in flash, resume, release core debug.
"""
import sys, os, time, subprocess
from pyocd.core.helpers import ConnectHelper
HERE = os.path.dirname(os.path.abspath(__file__))
NOTRAP = os.path.join(HERE, 'pyocd_notrap.py')   # disables pyOCD's RT1176 trap/mask hooks
ROM_PARK = 0x00223104
nm = subprocess.run([os.environ.get('ARM_NM', '/Applications/ARM_10/bin/arm-none-eabi-nm'), sys.argv[1]], capture_output=True, text=True).stdout
estack = next(int(l.split()[0], 16) for l in nm.splitlines() if l.endswith(' _estack'))
def session():
    s = ConnectHelper.session_with_chosen_probe(target_override='mimxrt1170_cm7', connect_mode='attach', frequency=4000000,
                                                options={'user_script': NOTRAP})
    s.open(); return s
sess = session(); t = sess.target
pc = t.read32(0xE000101C)
if pc != ROM_PARK:
    srmr = t.read32(0x40C04004)
    if (srmr >> 12) & 3: sys.exit('SRMR=0x%08X masks M7 reset requests; press SW1 once' % srmr)
    try:
        t.write32(0xE000ED0C, 0x05FA0004); t.flush()
    except Exception:
        pass
    print('reset requested (PC was 0x%08X)' % pc)
    try: sess.close()
    except Exception: pass
    deadline = time.time() + 5
    while True:
        time.sleep(0.2)
        try:
            sess = session(); t = sess.target
            pc = t.read32(0xE000101C)
            if pc == ROM_PARK: break
            sess.close()
        except Exception:
            pass
        if time.time() > deadline: sys.exit('ROM did not park (last PC 0x%08X)' % pc)
entry = t.read32(0x30001004)
if t.read32(0x30001000) != 0x412000D1 or not (0x30000000 <= entry < 0x34000000): sys.exit('no valid IVT at 0x30001000')
t.halt()
t.write_core_register('msp', estack)
t.write_core_register('pc', entry & ~1)
t.write_core_register('xpsr', 0x01000000)
t.write32(0xE000ED08, 0x30001000)
t.resume()
t.write32(0xE000EDF0, 0xA05F0000)
print('started image from ROM park: SP 0x%08X PC 0x%08X' % (estack, entry & ~1)); sys.stdout.flush()
os._exit(0)
