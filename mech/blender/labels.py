"""Label tables for the two shots.

key     unique name (objects are Label_<key>...)
text    what is shown; '\n' starts a second line
targets what the leaders point at: 'Object' (centre of its bounding box) or
        ('Object', (fx, fy, fz)[, (nx, ny, nz)]) = a point at those fractions of the
        box, nudged by mm in world axes
offset  label position relative to the middle of the targets, world mm (X east, Y toward
        the audio jacks, Z up); or anchor_board = (x, y) in board mm, on the component side
cue     frame the label starts to fade in; out = frame it starts to fade out (None = stays)
hold    a frame at which it is fully shown; the checks and preview stills use it
"""
import common as _C

TOP = (0.5, 0.5, 1.0)
# connector dots sit on the case's outer wall face: board edge + clearance + wall
WALL = _C.PARAMS['clear'] + _C.PARAMS['wall']

SCENE1 = [
    dict(key='c_display', text='5.5 inch touch display, 720 x 1280', targets=[('RK055_Screen', TOP)],
         offset=(0, 30, 45), cue=15, out=78, hold=50),
    dict(key='c_power', text='5 V power in', targets=[('J4', (0.0, 0.5, 0.5), (-WALL, 0, 0))],
         offset=(-6, 0, 42), cue=144, out=230, hold=195),
    dict(key='c_lineout', text='Line out', targets=[('J8', (0.5, 1.0, 0.5), (0, WALL, 0))],
         offset=(-20, 6, 42), cue=294, out=380, hold=345),
    dict(key='c_linein', text='Line in', targets=[('J9', (0.5, 1.0, 0.5), (0, WALL, 0))],
         offset=(20, 6, 42), cue=294, out=380, hold=345),
    dict(key='c_usbc', text='USB-C: device and power', targets=[('J3', (1.0, 0.5, 0.5), (WALL, 0, 0))],
         offset=(6, 12, 50), cue=444, out=530, hold=495),
    dict(key='c_usbhost', text='Micro-USB: host', targets=[('J2', (1.0, 0.5, 0.5), (WALL, 0, 0))],
         offset=(6, -28, 34), cue=444, out=530, hold=495),
    dict(key='c_sd', text='microSD card', targets=[('SD_Card', (0.5, 0.0, 0.5))],
         offset=(32, -6, 40), cue=594, out=680, hold=645),
    dict(key='c_ribbon', text='Display ribbon', targets=['Ribbon_Apex'],
         offset=(-40, 0, 34), cue=594, out=680, hold=645),
]

_A = dict(out=1316, hold=1290)
_B = dict(out=None, hold=1740)
_E = (1.0, 0.5, 0.5)


def _cue(i):
    return 1430 + 26 * i


SCENE2 = [
    dict(key='x_lid', text='Lid', targets=[('Lid', _E)], offset=(55, -20, 0), cue=1200, **_A),
    dict(key='x_rk055', text='RK055 display', targets=[('RK055_Carrier', _E)], offset=(55, -20, 0), cue=1212, **_A),
    dict(key='x_board', text='Nosh board', targets=[('J3', _E)], offset=(55, -20, 0), cue=1224, **_A),
    dict(key='x_tray', text='Tray', targets=[('Tray', (1.0, 0.5, 0.6))], offset=(55, -20, 0), cue=1236, **_A),

    dict(key='x_proc', text='i.MX RT1176 processor', targets=[('U1', TOP)], anchor_board=(25, -22), cue=_cue(0), **_B),
    dict(key='x_sdram', text='128 MB SDRAM', targets=[('U9', TOP), ('U10', TOP)], anchor_board=(-45, 22), cue=_cue(1), **_B),
    dict(key='x_flash', text='QSPI flash', targets=[('U2', TOP)], anchor_board=(88, -22), cue=_cue(2), **_B),
    dict(key='x_codec', text='SGTL5000 audio codec', targets=[('U15', TOP)], anchor_board=(182, 80), cue=_cue(3), **_B),
    dict(key='x_m2', text='M.2 Key E slot with\nWi-Fi / Bluetooth card', targets=[('M2_Card', TOP)],
         anchor_board=(150, -26), cue=_cue(4), **_B),
    dict(key='x_buck', text='3.3 V buck regulator', targets=[('U6', TOP)], anchor_board=(-36, 86), cue=_cue(5), **_B),
    dict(key='x_swd', text='SWD debug header', targets=[('J1', TOP)], anchor_board=(28, 108), cue=_cue(6), **_B),
    dict(key='x_uart', text='Debug UART', targets=[('J11', TOP)], anchor_board=(140, 108), cue=_cue(7), **_B),
    dict(key='x_reset', text='Reset', targets=[('SW1', TOP)], anchor_board=(190, 48), cue=_cue(8), **_B),
    dict(key='x_onoff', text='On/off and wake-up', targets=[('SW2', TOP), ('SW3', TOP)], anchor_board=(86, 108), cue=_cue(9), **_B),
    dict(key='x_boot', text='Boot-mode switch', targets=[('SW4', TOP)], anchor_board=(-45, 45), cue=_cue(10), **_B),
]
