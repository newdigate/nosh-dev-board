#!/usr/bin/env python3
# hwreset.py [ms]: pulse the probe's nRESET (J1.10 -> D1 -> POR_B) without touching the target.
import sys, time
from pyocd.probe.aggregator import DebugProbeAggregator
from pyocd.core.session import Session
ms = float(sys.argv[1]) if len(sys.argv) > 1 else 200
p = DebugProbeAggregator.get_all_connected_probes()[0]
sess = Session(p, target_override='mimxrt1170_cm7')
sess.open(init_board=False)
try:
    p.assert_reset(True)
    time.sleep(0.01)
    print('asserted; probe reads nRESET as', 'LOW' if p.is_reset_asserted() else 'HIGH (line not pulled low!)')
    time.sleep(ms / 1000)
    p.assert_reset(False)
    time.sleep(0.01)
    print('released; probe reads nRESET as', 'LOW (still held!)' if p.is_reset_asserted() else 'HIGH')
finally:
    sess.close()
