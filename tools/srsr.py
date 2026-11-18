#!/usr/bin/env python3
# srsr.py [clear]: attach (no halt, no trap hooks), read SRC_SRSR, optionally W1C-clear it.
import os, sys
from pyocd.core.helpers import ConnectHelper
HERE = os.path.dirname(os.path.abspath(__file__))
NOTRAP = os.path.join(HERE, 'pyocd_notrap.py')   # disables pyOCD's RT1176 trap/mask hooks
SRSR = 0x40C04010
NAMES = {0: 'POR_B(M7)', 1: 'M7_REQUEST', 2: 'M7_LOCKUP', 3: 'CSU', 4: 'USER_RESET', 5: 'WDOG', 6: 'JTAG_RST',
         7: 'JTAG_SW_RST', 8: 'WDOG3', 9: 'WDOG4', 10: 'TEMPSENSE', 11: 'M4_REQUEST', 12: 'M4_LOCKUP',
         13: 'OVERVOLT', 14: 'CDOG', 16: 'POR_B(M4)', 17: 'M4_REQUEST(M4)', 18: 'M4_LOCKUP(M4)', 27: 'M7_REQUEST(M4)',
         28: 'M7_LOCKUP(M4)'}
def dec(v): return ' '.join(n for b, n in NAMES.items() if v >> b & 1) or '-'
with ConnectHelper.session_with_chosen_probe(target_override='mimxrt1170_cm7', connect_mode='attach', frequency=4000000,
                                             options={'user_script': NOTRAP}) as sess:
    t = sess.target
    v = t.read32(SRSR); print('SRSR=0x%08X  %s' % (v, dec(v)))
    if len(sys.argv) > 1 and sys.argv[1] == 'clear':
        t.write32(SRSR, 0xFFFFFFFF); v = t.read32(SRSR); print('after clear SRSR=0x%08X  %s' % (v, dec(v)))
