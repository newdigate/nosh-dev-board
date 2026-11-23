"""Parameters for the Nosh enclosure. Edit here, then re-run build_enclosure.py.

Units mm. Board frame: origin at the board's NW corner, x east, y south.
Model frame: same x and y, z up with the display on top, z = 0 at the table side of the tray.
Each value is tagged: M = measured by the user, B = from the board file / STEP,
D = datasheet, C = design choice, A = assumed (confirm before printing).
"""

P = dict(
    # board and stack
    board_w=153.9,          # M  outline, long side
    board_h=81.8,           # M  outline, short side
    pcb_t=1.6,              # B  nominal board thickness
    step_comp_face_z=1.55,  # B  z of the component face in the exported STEP
    gap=16.0,               # M  between Nosh and the carrier (standoff nominal 16.1)
    carrier_t=2.0,          # M
    panel_t=4.0,            # M  glass surface above the carrier top (datasheet module 3.90)
    glass_x0=11.0,          # M  glass edge from the carrier's west edge
    glass_y0=2.0,           # M  glass edge from the ribbon-side edge (board y = 0)
    glass_w=133.96,         # D
    glass_h=79.24,          # D
    standoff_d=4.5,         # D  EVKB BOM (M3, 4.5 mm OD brass), not re-measured
    # ribbon
    ribbon_x=70.65,         # B  J7 centre
    ribbon_w=20.4,          # M
    ribbon_margin=2.0,      # C  each side of the ribbon in the window
    # shell
    wall=3.0,               # C  2.0 until 2026-11-23; thickened after the resin printer's warp warning
    clear=0.5,              # C  board edge to inner wall
    floor=2.0,              # C
    cavity=10.0,            # C  floor to the board's component face (J4 stands 9.0)
    plate=2.0,              # C  lid top plate
    face_below_glass=0.2,   # C
    window_gap=0.5,         # C  glass to window edge
    rim_gap=0.3,            # C  lid skirt to tray rim when closed
    tongue_t=1.0,           # C
    tongue_h=1.5,           # C
    tongue_fit=0.35,         # C  clearance of the lid rebate around the tongue
    corner_r=3.5,           # C  outer vertical corner radius
    boss_d=7.5,             # C
    pad_d=7.0,              # C / A  lid pad on the carrier; assumes the carrier is bare there
    screw_hole=3.4,         # C  M3 clearance
    csk_d=6.0,              # D  DIN 7991 M3 head
    csk_depth=1.3,          # C  90 degree cone from csk_d to screw_hole
    tray_screw=18.0,        # C  countersunk M3 length, tray side
    lid_screw=10.0,         # C  countersunk M3 length, lid side
    notch_margin=0.5,       # C  around each plug overmould
    merge_gap=3.0,          # C  join two notches when the post between them would be thinner
    sd_notch_depth=9.0,     # C  finger slot below the board face at J5
    sd_slot_w=20.0,         # C  finger slot width (a fingertip, not a nail)
    sd_relief=1.0,          # C  outer wall thinned by this much around the J5 slot (finger reach)
    sd_relief_side=6.0,     # C  relief extends this far either side of the slot
    sd_overtravel=0.8,      # A  push-to-eject travel beyond the locked position
    vent_n=6, vent_w=2.0, vent_l=20.0, vent_pitch=5.0, vent_at=(72.0, 42.0),  # C  under U1
)

# Edge connectors. u = position along the edge (board x or y), d = plug axis below the
# component face (None = take from the STEP), shape rect (w, h) or round (dia) = overmould.
PLUGS = [
    dict(ref='J3', edge='E', u=50.0, d=None, rect=(12.5, 6.5), src='overmould A, axis B'),
    dict(ref='J2', edge='E', u=36.0, d=1.4, rect=(11.0, 7.0), src='overmould A, axis A'),
    dict(ref='J4', edge='W', u=62.0, d=5.0, dia=11.0, src='overmould A, axis B (STEP bore)'),
    dict(ref='J8', edge='S', u=118.0, d=2.5, dia=10.0, src='overmould A, axis A'),
    dict(ref='J9', edge='S', u=131.0, d=2.5, dia=10.0, src='overmould A, axis A'),
]

# microSD: card slab used as keep-out. Locked card ends 1.075 past the edge (B, board notes).
SD = dict(ref='J5', edge='N', card_w=11.0, card_t=1.0, card_d=1.0, locked_out=1.075)

# Stand-in boxes for parts with no 3D model: ref -> height above its board face.
# All ASSUMED (recalled values); the makers' drawings were not re-read.
BOXES = dict(J2=2.8, J8=5.0, J9=5.0, J6=4.2, J7=2.0, H5=2.0, U1=1.5)
M2_CARD = dict(x0=114.0, x1=136.0, y0=10.0, y1=40.0, z_off=2.0, t=2.3)  # A  2230 card on the H5 nut


def levels(p=P):
    z = {}
    z['floor'] = p['floor']
    z['comp'] = p['floor'] + p['cavity']              # board component face
    z['split'] = z['comp'] + p['pcb_t']               # board display-side face = tray rim
    z['car0'] = z['split'] + p['gap']
    z['car1'] = z['car0'] + p['carrier_t']
    z['glass'] = z['car1'] + p['panel_t']
    z['face'] = z['glass'] - p['face_below_glass']
    z['plate0'] = z['face'] - p['plate']
    z['lid0'] = z['split'] + p['rim_gap']
    z['tongue'] = z['split'] + p['tongue_h']
    return z
