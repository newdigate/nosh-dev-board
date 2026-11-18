#!/usr/bin/env python3
# rstregs.py: attach (no halt, no trap hooks); print the registers that decide a warm reset.
import os
from pyocd.core.helpers import ConnectHelper
HERE = os.path.dirname(os.path.abspath(__file__))
NOTRAP = os.path.join(HERE, 'pyocd_notrap.py')   # disables pyOCD's RT1176 trap/mask hooks
R = [('SRC_SCR', 0x40C04000), ('SRC_SRMR', 0x40C04004), ('SRC_SBMR2', 0x40C0400C), ('SRC_SRSR', 0x40C04010),
     ('GPR26 (CM7 VTOR>>7)', 0x40C0C068), ('DWT_PCSR', 0xE000101C), ('DHCSR', 0xE000EDF0), ('VTOR', 0xE000ED08)]
with ConnectHelper.session_with_chosen_probe(target_override='mimxrt1170_cm7', connect_mode='attach', frequency=4000000,
                                             options={'user_script': NOTRAP}) as sess:
    t = sess.target
    for n, a in R:
        v = t.read32(a)
        extra = ('  -> boot VTOR 0x%08X' % (v << 7)) if 'GPR26' in n else ''
        print('%-20s 0x%08X%s' % (n, v, extra))
