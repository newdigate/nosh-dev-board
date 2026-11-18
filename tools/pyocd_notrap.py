# pyocd user script: stop the built-in MIMXRT1176 target from trapping the cores and
# masking their reset requests on connect/reset, so a SYSRESETREQ really reboots the SoC
# into the flash image. Use: pyocd ... -O user_script=<this file>
def will_init_target(target, init_sequence):
    for name in ("prepare_cm7_trap_code", "prepare_cm4_trap_code", "update_sbmr"):
        if hasattr(target, name):
            setattr(target, name, lambda ap, _n=name: None)
